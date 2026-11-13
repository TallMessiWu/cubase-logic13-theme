"""Generate a self-contained synthetic SVG from theme values; no screenshots."""
from pathlib import Path
import html
import json
import math

ROOT=Path(__file__).resolve().parents[1]
theme=json.loads((ROOT/'themes/logic13-graphite48.json').read_text(encoding='utf-8'))
colors=theme['track_colors']
parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1340" viewBox="0 0 1440 1340" role="img" aria-labelledby="title desc">',
       '<title id="title">Logic 13-inspired Graphite 48 for Cubase</title>',
       '<desc id="desc">Synthetic color demonstration, not an application screenshot. Dark surfaces, silver faders, green-yellow-red meters, and 48 track colors.</desc>',
       '<rect width="1440" height="1340" fill="#101012"/>',
       '<style>text{font-family:Segoe UI,Arial,sans-serif;fill:#E7E7EB}.muted{fill:#9797A6}.small{font-size:13px}.code{font-family:Consolas,monospace;font-size:12px;fill:#B3B3C1}</style>']

def rect(x,y,w,h,fill,rx=0,stroke=None):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"'+(f' stroke="{stroke}"' if stroke else '')+'/>')

def text(x,y,value,size=14,cls=''):
    parts.append(f'<text x="{x}" y="{y}" font-size="{size}" class="{cls}">{html.escape(value)}</text>')

text(48,43,'CUBASE  /  LOGIC PRO 13 INSPIRED',13,'muted')
text(48,87,'Graphite 48',36)
text(48,117,'Near-black workspace. Silver controls. Vivid content colors.',17,'muted')
rect(48,147,1344,48,'#28282A',8)
text(68,178,'SYNTHETIC PREVIEW',13)
text(1080,178,'120.000   |   4/4',14,'code')
for i in range(8):
    y=197+i*43
    color='#'+colors[i]['color']
    rect(48,y,225,41,'#242426')
    rect(48,y,5,41,color)
    text(68,y+26,f'Track {i+1:02d}',13)
    text(192,y+26,'M  S',11,'muted')
    rect(275,y,1117,41,'#141416')
    for bar in range(1,12):
        rect(275+bar*93,y,1,41,'#303034')
    left=282+[0,93,0,186,93,372,0,186][i]
    width=[900,710,1090,780,990,570,1090,780][i]
    rect(left,y+4,width,33,color,3)
    path=' '.join(('M' if x==0 else 'L')+f'{left+x},{y+21+8*math.sin(x*.27+i)*math.sin(x*.071):.2f}' for x in range(0,width,4))
    parts.append(f'<path d="{path}" stroke="#FFF" stroke-opacity=".75" fill="none" stroke-width="1.2"/>')
text(48,572,'SILVER FADERS / RESTRAINED FUNCTION COLORS',13,'muted')
faders=list(dict.fromkeys(theme['group_colors']['FaderColorPreferences'].values()))[:8]
strips=list(theme['group_colors']['StripColorPreferences'].values())
for i,color in enumerate(faders):
    x=48+i*88
    rect(x,588,78,112,'#242426',5)
    rect(x+7,596,64,13,'#'+strips[i%len(strips)],2)
    rect(x+29,620,5,66,'#101012',2)
    rect(x+19,642+(i%3)*5,25,14,'#'+color,2)
    rect(x+56,643,6,43,'#329B64')
    rect(x+56,634,6,9,'#6BCD76')
    rect(x+56,626,6,8,'#E9B44C')
    rect(x+56,620,6,6,'#E85B64')
for i,(label,field) in enumerate([('Panel','1000'),('Workspace','4000'),('Editor','4100'),('Focus','1100'),('Cycle','4202')]):
    x=800+(i%3)*195;y=591+(i//3)*57
    hexcolor=theme['surface'][field]['color']
    rect(x,y,25,25,'#'+hexcolor,4,'#44444C')
    text(x+36,y+13,label,12)
    text(x+36,y+31,'#'+hexcolor,12,'code')
for band,label in enumerate(['01–16  PRIMARY','17–32  SOFT','33–48  DEEP']):
    top=744+band*173
    text(48,top,label,14,'muted')
    for j in range(16):
        c=colors[band*16+j]
        x=48+(j%8)*170;y=top+17+(j//8)*69
        rect(x,y,154,56,'#202023',5)
        rect(x,y,154,26,'#'+c['color'],4)
        text(x+8,y+44,c['name'].split(' ',1)[0]+'  #'+c['color'],12,'code')
text(48,1300,'Custom design, not official Apple color tokens. This graphic contains no real project or user data.',12,'muted')
parts.append('</svg>')
output=ROOT/'docs/preview.svg'
output.parent.mkdir(parents=True,exist_ok=True)
output.write_text('\n'.join(parts)+'\n',encoding='utf-8')
print('Generated',output.relative_to(ROOT))
