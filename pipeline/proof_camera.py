"""Follow the visible orange pointer in the recorded pixels to compose readable close-ups."""
import subprocess
import numpy as np


def follow(clip, slots):
    width, height, rate = 188, 106, 10
    raw = subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(clip),
                          "-vf",f"fps={rate},scale={width}:{height}","-pix_fmt","rgb24",
                          "-f","rawvideo","pipe:1"],capture_output=True,check=True).stdout
    frames=np.frombuffer(raw,np.uint8).reshape(-1,height,width,3)
    outputs={}
    for slot,window in slots.items():
        cx,cy=.46,.42
        points=[]
        begin=round(window["start"]*rate)
        for rgb in frames[begin:begin+round(window["dur"]*rate)]:
            red,green,blue=np.moveaxis(rgb,-1,0)
            mask=(red>218)&(green>134)&(green<189)&(blue>35)&(blue<103)
            yy,xx=np.nonzero(mask)
            if len(xx)>=3:
                # The pointer is a small triangular cluster. Large colored surfaces are irrelevant.
                groups={}
                for x,y in zip(xx.tolist(),yy.tolist()):
                    key=(x//5,y//5);groups.setdefault(key,[]).append((x,y))
                candidates=[v for v in groups.values() if 3<=len(v)<=14]
                if candidates:
                    cluster=max(candidates,key=lambda v:len(v)-.012*abs(v[0][0]-cx*width))
                    px,py=np.mean(cluster,axis=0)
                    cx+=.44*(px/width-cx);cy+=.44*(py/height-cy)
            points.append([round(cx,3),round(cy,3)])
        outputs[slot]=points
    return outputs

