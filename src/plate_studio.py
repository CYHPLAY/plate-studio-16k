"""Desktop adaptation of chinese_license_plate_generator (MIT, leijd 2020)."""
from pathlib import Path
import sys
import random
import json
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageDraw

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
TYPES = {'蓝牌 / 普通汽车': 'blue', '黄牌 / 中大型汽车': 'yellow',
         '绿牌 / 新能源小型汽车': 'green_car', '绿牌 / 新能源大型汽车': 'green_truck',
         '白牌 / 警车': 'white', '白牌 / 军车': 'white_army',
         '黑牌 / 港澳及领馆': 'black', '黑牌 / 使馆': 'black_shi'}
PROVINCES = '京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼'
LETTERS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'

def normalize(number):
    return ''.join(c for c in number.upper() if c not in ' ·.‐-\t\r\n')

def glyph_key(number, style, double, i):
    if style.startswith('green'):
        return 'green_' + number[i]
    height = 220 if double else 140
    key = f'{height}_{number[i]}'
    if (ROOT / 'font_model' / (key + '.jpg')).exists():
        return key
    return f'220_{"up" if i < 2 else "down"}_{number[i]}'

def validate(number, style, double, width):
    expected = 8 if style.startswith('green') else 7
    if len(number) != expected:
        raise ValueError(f'此类型需要 {expected} 位字符（不包含分隔点）。')
    if double and style not in ('yellow', 'white'):
        raise ValueError('项目素材仅支持黄牌和普通白牌的双层样式。')
    if not 440 <= width <= 16000:
        raise ValueError('导出宽度请设置为 440～16000 像素。')
    for i, char in enumerate(number):
        if not (ROOT / 'font_model' / (glyph_key(number, style, double, i) + '.jpg')).exists():
            raise ValueError(f'当前样式没有字符“{char}”的素材。请选择其他字符或样式。')

def positions(number, double):
    if double:
        return [(110, 15, 190, 75), (250, 15, 330, 75)] + [(27+(i-2)*80,90,92+(i-2)*80,200) for i in range(2,7)]
    split = 1 if '警' in number else 4 if '使' in number else 2
    boxes = []
    for i in range(len(number)):
        x = 15 if i == 0 else boxes[-1][2] + ((34 if len(number)==7 else 49) if i==split else (12 if len(number)==7 else 9))
        boxes.append((x,25,x+(43 if len(number)==8 and i>0 else 45),115))
    return boxes

def draw_background(style, double, width, height, base_w, base_h, number):
    # All large visible elements are geometry, never enlarged template pixels.
    colors = {'blue':'#071c78','yellow':'#ffbd00','black':'#060606',
              'black_shi':'#060606','white':'#ffffff','white_army':'#ffffff',
              'green_car':'#08d36d','green_truck':'#08ce67'}
    im = Image.new('RGB',(width,height),colors[style])
    if style=='green_car':
        top,bottom = np.array([205,255,229]),np.array([0,210,100])
        gradient = np.round(top[None,:]+(bottom-top)[None,:]*np.linspace(0,1,height)[:,None]).astype(np.uint8)
        im = Image.fromarray(np.repeat(gradient[:,None,:],width,axis=1))
    draw = ImageDraw.Draw(im)
    sx,sy = width/base_w,height/base_h
    box = lambda coords: tuple(round(v*(sx if i%2==0 else sy)) for i,v in enumerate(coords))
    if style=='green_truck':
        draw.rectangle(box((0,0,137,base_h)),fill='#ffbd00')
    border = '#ffffff' if style in ('blue','black','black_shi') else '#111111'
    border_width = 1.6
    draw.rounded_rectangle(box((2,2,base_w-3,base_h-3)),radius=round(10*min(sx,sy)),outline=border,width=max(1,round(border_width*min(sx,sy))))
    holes = '#ffffff' if style in ('blue','black','black_shi','yellow','white','white_army') else '#101010'
    for x in (base_w*.25,base_w*.75):
        for y in (13,base_h-13):
            draw.rounded_rectangle(box((x-11,y-3.8,x+11,y+3.8)),radius=max(1,round(3.8*min(sx,sy))),fill=holes,
                                   outline='#777777' if style.startswith('white') else holes,width=max(1,round(.5*sx)))
    split = 1 if '警' in number else 4 if '使' in number else 2
    if double:
        cx,cy = 220,42
    else:
        boxes = positions(number,False)
        cx,cy = (boxes[split-1][2]+boxes[split][0])/2,70
    if style.startswith('green'):
        # Simple geometric separator, avoids the unreadable low-resolution emblem.
        draw.ellipse(box((cx-5,cy-5,cx+5,cy+5)),fill='#111111')
    else:
        dot = '#ffffff' if style in ('blue','black','black_shi') else '#111111'
        draw.ellipse(box((cx-4.5,cy-4.5,cx+4.5,cy+4.5)),fill=dot)
    return im

def smooth_contour(contour, digit=False):
    pts = cv2.approxPolyDP(contour, .65, True).reshape(-1,2).astype(np.float64)
    if len(pts) < 3:
        return pts.reshape(-1,1,2)
    # Remove raster stair steps, then round only at sub-pixel source scale.
    for _ in range(2):
        following = np.roll(pts,-1,axis=0)
        ratio = .125
        pts = np.stack(((1-ratio)*pts+ratio*following,ratio*pts+(1-ratio)*following),axis=1).reshape(-1,2)
    return pts.reshape(-1,1,2)

def emboss_region(region, mask, color, scale, strength):
    alpha = mask.astype(np.float32)/255
    reduction = max(1,int(scale/6))
    small = cv2.resize(mask,(max(2,mask.shape[1]//reduction),max(2,mask.shape[0]//reduction)),interpolation=cv2.INTER_AREA) if reduction>1 else mask
    field_scale = scale/reduction
    binary = (small>127).astype(np.uint8)
    inner = cv2.distanceTransform(binary,cv2.DIST_L2,5)
    outer = cv2.distanceTransform(1-binary,cv2.DIST_L2,5)
    bevel = max(1.0,1.15*field_scale)
    field = np.clip((inner-outer)/bevel,-1,1)
    field = cv2.GaussianBlur(field,(0,0),max(.5,.22*field_scale))
    gy,gx = np.gradient(field)
    light = np.clip((gx*.7+gy*.85)*bevel,-1,1)
    # A narrow bright metal rim surrounds the printed raised face.
    rim = np.clip(1-outer/(1.5*field_scale),0,1)
    if reduction>1:
        light = cv2.resize(light,(mask.shape[1],mask.shape[0]),interpolation=cv2.INTER_LINEAR)
        rim = cv2.resize(rim,(mask.shape[1],mask.shape[0]),interpolation=cv2.INTER_LINEAR)
    rim *= 1-alpha
    # Slight directional cast shadow makes the raised thickness legible.
    offset = max(1,round(.7*scale))
    shadow = np.zeros_like(alpha)
    shadow[offset:,offset:] = alpha[:-offset,:-offset]
    shadow = cv2.GaussianBlur(shadow,(0,0),max(.5,.35*scale))*(1-alpha)
    # Compose short strips to avoid multiple full-size RGB float buffers.
    base_color = np.array(color,dtype=np.float32)+(12 if max(color)<100 else 0)
    for start in range(0,region.shape[0],128):
        end = min(start+128,region.shape[0])
        illumination = light[start:end]
        highlight = np.clip(illumination,0,1)*strength
        shade = np.clip(-illumination,0,1)*strength
        face = base_color[None,None,:]+highlight[:,:,None]*105
        face *= 1-shade[:,:,None]*.60
        result = region[start:end].astype(np.float32)
        amount = rim[start:end]*strength*.70
        metal = np.clip(140+illumination*110,25,250)
        result = result*(1-amount[:,:,None])+metal[:,:,None]*amount[:,:,None]
        opacity = alpha[start:end,:,None]
        result = result*(1-opacity)+np.clip(face,0,255)*opacity
        result *= 1-shadow[start:end,:,None]*.25*strength
        region[start:end] = np.clip(result,0,255).astype(np.uint8)
    return region

def render_plate(number, style='blue', double=False, width=3840, relief=True, strength=1.0):
    number = normalize(number)
    validate(number, style, double, width)
    base_w, base_h = (480 if len(number)==8 else 440), (220 if double else 140)
    height = round(width*base_h/base_w)
    output_size = (width,height)
    # Supersample preview and normal exports; 8K already has enough edge samples.
    aa = 2 if width<=3840 else 1
    width,height = width*aa,height*aa
    background = draw_background(style,double,width,height,base_w,base_h,number)
    canvas = np.array(background)
    del background
    band = max(2,round(6*output_size[0]/base_w))
    w,h = output_size
    bounds_list = ((0,0,w,band),(0,h-band,w,h),(0,0,band,h),(w-band,0,w,h))
    border_pieces = []
    if relief:
        for bounds in bounds_list:
            scaled = tuple(v*aa for v in bounds)
            x0,y0,x3,y3 = scaled
            patch = Image.fromarray(canvas[y0:y3,x0:x3])
            if aa>1:
                patch = patch.resize((bounds[2]-bounds[0],bounds[3]-bounds[1]),Image.Resampling.LANCZOS)
            border_pieces.append(patch)
    if relief:
        strength = max(0,min(1.5,float(strength)))
        # Broad reflection across the face; calculate row by row to limit 8K memory.
        for y in range(height):
            t = y/max(1,height-1)
            factor = 1-.07*strength + .09*strength*np.exp(-((t-.27)/.30)**2)
            canvas[y] = np.clip(canvas[y].astype(np.float32)*factor,0,255).astype(np.uint8)
    for i, box in enumerate(positions(number,double)):
        with Image.open(ROOT / 'font_model' / (glyph_key(number,style,double,i)+'.jpg')) as src:
            gray = np.array(src.convert('L'))
        # Trace original glyphs, then rasterize their outlines at export resolution.
        contours, hierarchy = cv2.findContours((gray<200).astype(np.uint8)*255, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        x1,y1,x2,y2 = box
        x1,x2 = round(x1*width/base_w),round(x2*width/base_w)
        y1,y2 = round(y1*height/base_h),round(y2*height/base_h)
        mask = np.zeros((y2-y1,x2-x1),np.uint8)
        transformed = [np.round(smooth_contour(c,number[i].isdigit())*np.array([(x2-x1)/gray.shape[1],(y2-y1)/gray.shape[0]])).astype(np.int32) for c in contours]
        if transformed:
            cv2.drawContours(mask, transformed, -1, 255, cv2.FILLED, cv2.LINE_AA, hierarchy=hierarchy)
        if number[i].isdigit():
            # Reconstruct the original silhouette with subpixel level sets.
            # Filtering at source scale removes stair steps without redesigning strokes.
            factor = 6
            dense = cv2.resize(gray.astype(np.float32),(gray.shape[1]*factor,gray.shape[0]*factor),interpolation=cv2.INTER_CUBIC)
            dense = cv2.GaussianBlur(dense,(0,0),factor*.45)
            dense_contours,dense_hierarchy = cv2.findContours((dense<160).astype(np.uint8)*255,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
            paths = []
            for c in dense_contours:
                pts = cv2.approxPolyDP(c,factor*.8,True).reshape(-1,2).astype(float)
                # Subdivide rounded arcs while locking sharp corners of 1 and 5.
                for _ in range(3):
                    before,after = np.roll(pts,1,axis=0),np.roll(pts,-1,axis=0)
                    u,v = pts-before,after-pts
                    cosine = np.sum(u*v,axis=1)/np.maximum(1e-9,np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1))
                    locked = cosine<.65
                    rebuilt = []
                    for j,p in enumerate(pts):
                        if locked[j]: rebuilt.append(p)
                        else: rebuilt.extend((.75*p+.25*before[j],.75*p+.25*after[j]))
                    pts = np.array(rebuilt)
                paths.append(np.round(pts.reshape(-1,1,2)*np.array([(x2-x1)/dense.shape[1],(y2-y1)/dense.shape[0]])).astype(np.int32))
            mask[:] = 0
            if paths:
                cv2.drawContours(mask,paths,-1,255,cv2.FILLED,cv2.LINE_AA,hierarchy=dense_hierarchy)
        red = number[i] in '警使领' or (style=='white_army' and i<2)
        color = (220,20,28) if red else (255,255,255) if style in ('blue','black','black_shi') else (0,0,0)
        if relief:
            pad = max(4,round(width/base_w*4))
            left,top = max(0,x1-pad),max(0,y1-pad)
            right,bottom = min(width,x2+pad),min(height,y2+pad)
            padded = np.zeros((bottom-top,right-left),np.uint8)
            padded[y1-top:y2-top,x1-left:x2-left] = mask
            canvas[top:bottom,left:right] = emboss_region(canvas[top:bottom,left:right],padded,color,width/base_w,strength)
            del padded
        else:
            alpha = mask.astype(np.float32)[:,:,None]/255
            region = canvas[y1:y2,x1:x2]
            region[:] = np.round(region*(1-alpha)+np.array(color)*alpha).astype(np.uint8)
    del mask
    image = Image.fromarray(canvas)
    del canvas
    image = image.resize(output_size,Image.Resampling.LANCZOS) if aa>1 else image
    if relief:
        # Restore the entire outer frame from v2, including its antialiased pixels.
        for bounds,patch in zip(bounds_list,border_pieces):
            image.paste(patch,bounds[:2])
    return image

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('高清车牌生成器 · 平滑立体版 16K')
        self.root.geometry('1000x690')
        self.root.minsize(880,620)
        self.root.configure(bg='#f1f5f9')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.',font=('Microsoft YaHei UI',11))
        style.configure('TButton',padding=9)
        self.number = tk.StringVar(value='京A12345')
        self.kind = tk.StringVar(value=next(iter(TYPES)))
        self.double = tk.BooleanVar()
        self.relief = tk.BooleanVar(value=True)
        self.strength = tk.DoubleVar(value=.7)
        self.width = tk.StringVar(value='3840')
        self.status = tk.StringVar(value='')
        self.pending = None
        self.exporting = False
        self.export_results = queue.Queue()
        outer = ttk.Frame(self.root,padding=24)
        outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='高清车牌生成器',font=('Microsoft YaHei UI',23,'bold')).pack(anchor='w')
        ttk.Label(outer,text='自定义号码 · 8 种底板 · 单层 / 双层 · 高清图片导出',foreground='#64748b').pack(anchor='w',pady=(4,18))
        controls = ttk.Frame(outer)
        controls.pack(fill='x')
        for col, label in enumerate(('车牌号码','车牌类型','导出宽度（像素）')):
            ttk.Label(controls,text=label).grid(row=0,column=col,sticky='w',pady=5)
        self.entry = ttk.Entry(controls,textvariable=self.number,width=20,font=('Microsoft YaHei UI',17))
        self.entry.grid(row=1,column=0,sticky='ew',padx=(0,16))
        ttk.Combobox(controls,textvariable=self.kind,values=list(TYPES),state='readonly',width=27).grid(row=1,column=1,sticky='ew',padx=(0,16))
        ttk.Combobox(controls,textvariable=self.width,values=['1920','3840','4400','7680','12000','16000'],width=14).grid(row=1,column=2,sticky='ew')
        controls.columnconfigure(0,weight=1)
        controls.columnconfigure(1,weight=1)
        bar = ttk.Frame(outer)
        bar.pack(fill='x',pady=16)
        ttk.Checkbutton(bar,text='双层车牌（黄牌 / 白牌）',variable=self.double).pack(side='left')
        ttk.Button(bar,text='随机号码',command=self.randomize).pack(side='right')
        effects = ttk.Frame(outer)
        effects.pack(fill='x',pady=(0,12))
        ttk.Checkbutton(effects,text='立体压凸效果',variable=self.relief).pack(side='left')
        ttk.Label(effects,text='  强度').pack(side='left')
        ttk.Scale(effects,from_=0.2,to=1.5,variable=self.strength,length=200).pack(side='left',padx=10)
        self.preview = tk.Canvas(outer,bg='#162235',height=275,highlightthickness=0)
        self.preview.pack(fill='both',expand=True)
        self.preview.bind('<Configure>',lambda e:self.schedule())
        ttk.Label(outer,textvariable=self.status,foreground='#475569',wraplength=920).pack(anchor='w',pady=12)
        footer = ttk.Frame(outer)
        footer.pack(fill='x')
        ttk.Label(footer,text='PNG 无损 / JPG 高质量，保持原始比例\n用于设计预览及合成数据；号码组合不做登记规则校验。',foreground='#64748b',font=('Microsoft YaHei UI',10)).pack(side='left')
        ttk.Button(footer,text='导出图片…',command=self.export).pack(side='right')
        for var in (self.number,self.kind,self.double,self.width,self.relief,self.strength):
            var.trace_add('write',self.schedule)
        self.root.bind('<Control-s>',lambda e:self.export())
        self.root.after(100,self.update_preview)

    def schedule(self,*args):
        if self.pending:
            self.root.after_cancel(self.pending)
        self.pending = self.root.after(180,self.update_preview)

    def settings(self):
        try:
            width = int(self.width.get())
        except ValueError:
            raise ValueError('导出宽度必须是整数。')
        return normalize(self.number.get()),TYPES[self.kind.get()],self.double.get(),width

    def update_preview(self):
        self.pending = None
        self.preview.delete('all')
        try:
            n,s,d,w = self.settings()
            validate(n,s,d,w)
            im = render_plate(n,s,d,min(1400,w),self.relief.get(),self.strength.get())
            im.thumbnail((max(100,self.preview.winfo_width()-64),max(80,self.preview.winfo_height()-40)),Image.Resampling.LANCZOS)
            self.photo = ImageTk.PhotoImage(im)
            self.preview.create_image(self.preview.winfo_width()//2,self.preview.winfo_height()//2,image=self.photo)
            h = round(w*(220 if d else 140)/(480 if len(n)==8 else 440))
            self.status.set(f'{n}  ·  导出尺寸 {w} × {h} 像素  ·  输入小写字母会自动转为大写')
        except Exception as e:
            self.status.set(str(e))
            self.preview.create_text(self.preview.winfo_width()//2,self.preview.winfo_height()//2,text=str(e),fill='#e2e8f0',font=('Microsoft YaHei UI',13),width=700)

    def randomize(self):
        s = TYPES[self.kind.get()]
        if s not in ('yellow','white'):
            self.double.set(False)
        digits = lambda k: ''.join(random.choices('0123456789',k=k))
        prefix = random.choice(PROVINCES)+random.choice(LETTERS)
        if s=='green_car': n = prefix+random.choice('DF')+digits(5)
        elif s=='green_truck': n = prefix+digits(5)+random.choice('DF')
        elif s=='white_army': n = 'VA'+digits(5)
        elif s=='white' and not self.double.get(): n = prefix+digits(4)+'警'
        elif s=='black_shi': n = digits(6)+'使'
        elif s=='black': n = '粤Z'+''.join(random.choices(LETTERS+'0123456789',k=4))+random.choice('港澳')
        else: n = prefix+''.join(random.choices(LETTERS+'0123456789',k=5))
        self.number.set(n)

    def export(self):
        if self.exporting:
            return
        try:
            settings = self.settings()
            validate(*settings)
            path = filedialog.asksaveasfilename(title='保存高清车牌',initialfile=settings[0]+'.png',defaultextension='.png',filetypes=[('PNG 无损图片','*.png'),('JPEG 图片','*.jpg')])
            if not path: return
            suffix = Path(path).suffix.lower()
            if suffix not in ('.png','.jpg','.jpeg'):
                raise ValueError('请使用 .png 或 .jpg 文件扩展名。')
            self.root.configure(cursor='watch')
            self.root.update_idletasks()
            relief,strength = self.relief.get(),self.strength.get()
            self.exporting = True
            self.status.set('正在生成并保存高清图片，请稍候…')
            def worker():
                try:
                    image = render_plate(*settings,relief=relief,strength=strength)
                    image.save(path,format='PNG' if suffix=='.png' else 'JPEG',**({'compress_level':1} if suffix=='.png' else {'quality':98,'subsampling':0}))
                    self.export_results.put((True,path,image.size))
                except Exception as e:
                    self.export_results.put((False,str(e),None))
            threading.Thread(target=worker,daemon=True).start()
            self.root.after(100,self.poll_export)
        except Exception as e:
            messagebox.showerror('无法导出',str(e))
        finally:
            if not self.exporting:
                self.root.configure(cursor='')

    def poll_export(self):
        try:
            success,value,size = self.export_results.get_nowait()
        except queue.Empty:
            self.root.after(100,self.poll_export)
            return
        self.exporting = False
        self.root.configure(cursor='')
        if success:
            self.status.set(f'已保存：{value}（{size[0]} × {size[1]}）')
            messagebox.showinfo('导出完成',f'图片已保存到：\n{value}')
        else:
            self.status.set('导出失败：'+value)
            messagebox.showerror('无法导出',value)

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        cases = [('京A12345','blue',False),('沪AD12345','green_car',False),('粤A12345F','green_truck',False),('鲁B12345','yellow',True),('京A1234警','white',False),('VA12345','white_army',False),('粤Z1234港','black',False),('123456使','black_shi',False),('京A12345','white',True)]
        out = Path(sys.argv[sys.argv.index('--self-test')+1])
        out.mkdir(parents=True,exist_ok=True)
        results = []
        for index,(n,s,d) in enumerate(cases):
            image = render_plate(n,s,d,1920)
            image.save(out/f'{index}_{s}.png')
            results.append({'number':n,'style':s,'double':d,'size':image.size})
        (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        App().root.mainloop()
