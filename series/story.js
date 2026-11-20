/* Shared drawing and live-footage primitives. Each story owns its stage and choreography. */
(() => {
  const K = window.KIT;
  const font = '"Microsoft YaHei","Noto Sans CJK SC",sans-serif';
  const progress = (t, delay = 0, seconds = 1) => {
    const u = Math.max(0, Math.min(1, (t - delay) / seconds));
    return u * u * (3 - 2 * u);
  };
  function box(g,x,y,w,h,color,r=0) {
    g.fillStyle=color; g.beginPath(); g.roundRect(x,y,w,h,r); g.fill();
  }
  function label(g,value,x,y,size,color,width=940,weight=750) {
    g.fillStyle=color; g.font=weight+' '+size+'px '+font;
    g.textBaseline='middle'; g.fillText(value,x,y,width);
  }
  function path(g,points,color,width=4,fill=false) {
    g.beginPath(); points.forEach(([x,y],i)=>i?g.lineTo(x,y):g.moveTo(x,y));
    if(fill){g.closePath();g.fillStyle=color;g.fill();}
    else {g.strokeStyle=color;g.lineWidth=width;g.lineJoin='round';g.stroke();}
  }
  function circle(g,x,y,r,color) {
    g.beginPath(); g.arc(x,y,r,0,Math.PI*2); g.fillStyle=color; g.fill();
  }
  function at(g,x,y,rotation,draw) {
    g.save(); g.translate(x,y); g.rotate(rotation); draw(); g.restore();
  }
  function live(g,s,t,H,x,y,w,bar,ink,title) {
    const im=H.frame(s,t);
    if(!im) throw Error('缺少本次操作录屏');
    const h=w*im.height/im.width;
    box(g,x-5,y-53,w+10,h+59,bar,6);
    label(g,title+'  ·  样例实录',x+14,y-25,30,ink,w-20);
    g.drawImage(im,x,y,w,h);
  }
  function measured(g,s,t,x,y,color) {
    if(t>=(s.hook_result_at??1.7)) label(g,s.hook_status,x,y,40,color,936);
  }
  function scene(story,stage,opts,paint) {
    const name=story+'_'+stage;
    window.VISUALS[name]={
      bg:opts.bg,
      build(s,id,H) {
        const media=opts.media?.(s,id,H)||'';
        const claim=stage==='claim'?K.ctaBlock(id+'cta',s,H,{x:75,y:1060,w:550}).html:'';
        return K.layers(id,'<canvas width="1080" height="1920" id="'+id+'story"></canvas>'+media+claim);
      },
      anim(s,id,t,H) {
        const g=H.$(id+'story').getContext('2d');
        g.save(); box(g,0,0,1080,1920,opts.bg);
        // A small camera move marks each edit beat. Keep the evidence pane inside the safe area.
        const beats=opts.beats, cycle=beats[beats.length-1]+1.3;
        const time=t%cycle;
        const accent=beats.reduce((v,b)=>v+Math.sin(Math.PI*Math.min(1,Math.max(0,(time-b)/.42))),0);
        const zoom=1+.012*Math.sin(t*1.3)+.035*accent;
        g.translate(540+6*Math.sin(1.6*t),815+5*Math.cos(1.3*t));
        g.scale(zoom,zoom);g.translate(-540,-815);
        paint(g,s,t,H,stage,id); g.restore();
        if(stage==='claim') K.ctaBlock(id+'cta',s,H,{x:75,y:1060,w:550}).anim(t,{show:.5,follow:1.65,type:2.65,send:3.85});
      },
      sfx:()=>opts.beats.map((at,i)=>[at,i===opts.beats.length-1?'ding':'tick'])
    };
  }
  window.STORY={box,label,path,circle,at,live,measured,progress,scene};
})();
