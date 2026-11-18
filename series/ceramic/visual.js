/* One film, six scenes. All measurements use the 1080 x 1920 master. */
(() => {
  const K = window.KIT, M = window.MO;
  const art = new URL("cup-turntable.webp", document.currentScript.src).href;
  const BG = {seed:43,base:["#18332c","#10261f","#081a17"],hue:[61,127,99],hue2:[22,88,71],hue3:[193,125,55],grid:false,dust:14};
  const ink="#15392f", cream="#f4edda", orange="#ff7940", yellow="#ffd369", light="#e8ead5";
  const sans='"Microsoft YaHei","Noto Sans CJK SC",sans-serif', mono='Consolas,"Courier New",monospace';
  const clamp=x=>Math.max(0,Math.min(1,x));
  const ramp=(t,a,d=.5)=>M.tw(t,a,d,'outC');
  const ease=(t,a,d=.5)=>M.tw(t,a,d,'inOutC');
  const mix=(a,b,p)=>a+(b-a)*p;
  const color=(g,c)=>{g.fillStyle=c};
  function rect(g,x,y,w,h,fill,r=0) {g.beginPath();g.roundRect(x,y,w,h,r);color(g,fill);g.fill();}
  function line(g,x,y,X,Y,c,w=2) {g.beginPath();g.moveTo(x,y);g.lineTo(X,Y);g.strokeStyle=c;g.lineWidth=w;g.stroke();}
  function ellipse(g,x,y,rx,ry,c) {g.beginPath();g.ellipse(x,y,rx,ry,0,0,Math.PI*2);color(g,c);g.fill();}
  function txt(g,s,x,y,size,c=ink,opt={}) {
    g.save();g.font=(opt.weight||750)+' '+size+'px '+(opt.mono?mono:sans);
    g.textAlign=opt.align||'left';g.textBaseline='middle';color(g,c);g.fillText(s,x,y,opt.max||1050);g.restore();
  }
  function transformed(g,x,y,rad,scale,alpha,draw) {
    g.save();g.translate(x,y);g.rotate(rad);g.scale(scale,scale);g.globalAlpha*=clamp(alpha);draw();g.restore();
  }
  function barcode(g,x,y,w,h,c) {
    let at=0; for(let i=0;at<w;i++){const n=[3,1,5,2,2,4,1,3,2,1,6][i%11]*2;
      if(i%2===0) rect(g,x+at,y,Math.min(n,w-at),h,c);at+=n;}
  }
  function shadow(g,draw) {g.save();g.shadowColor='rgba(8,26,20,.27)';g.shadowBlur=24;g.shadowOffsetY=15;draw();g.restore();}
  function toothed(g,x,y,w,h,c) {
    g.beginPath();g.moveTo(x,y);g.lineTo(x+w,y);g.lineTo(x+w,y+h);
    const n=Math.floor(w/22);for(let i=n;i>0;i--){g.lineTo(x+(i-.5)*w/n,y+h-8);g.lineTo(x+(i-1)*w/n,y+h);}
    g.closePath();color(g,c);g.fill();
  }
  function pill(g,s,x,y,w,bg,fg) {rect(g,x,y,w,64,bg,32);txt(g,s,x+w/2,y+31,32,fg,{align:'center'});}
  function cropText(g,s,x,y,size,t,start,c) {
    Array.from(s).forEach((ch,i)=>{const p=ramp(t,start+i*.047,.40);g.save();g.globalAlpha*=p;
      txt(g,ch,x+i*size*.98,y+46*(1-p),size,c,{weight:900});g.restore();});
  }
  function mast(g,sc,t,dark) {
    const fg=dark?cream:ink;const a=ramp(t,0,.34);g.save();g.globalAlpha*=a;
    rect(g,83,170,14,32,orange);txt(g,sc.eyebrow,113,186,31,fg);
    line(g,82,230,993,230,dark?'#a1b39a':'#687b68',2);
    barcode(g,822,170,168,33,fg);g.restore();
  }
  function headline(g,sc,t,dark) {
    mast(g,sc,t,dark);cropText(g,sc.head[0],76,334,103,t,.06,dark?cream:ink);
    cropText(g,sc.head[1],76,465,111,t,.23,dark?yellow:ink);
  }
  function paper(g,t){
    rect(g,-120,-160,1320,2280,cream);
    g.save();g.strokeStyle='#ddd7c6';g.lineWidth=1.8;
    for(let j=-3;j<25;j++){const yy=j*91+(t*8)%91;g.beginPath();g.moveTo(-60,yy+30);g.lineTo(1160,yy);g.stroke();}
    g.restore();
  }
  function orbit(g,x,y,r,t,dark=true) {
    g.save();g.translate(x,y);g.rotate(t*.14);
    for(let i=0;i<72;i++){const a=i*Math.PI/36;const big=i%6===0;
      line(g,Math.cos(a)*(r-(big?24:9)),Math.sin(a)*(r-(big?24:9)),Math.cos(a)*r,Math.sin(a)*r,dark?'rgba(230,239,205,.54)':'rgba(21,57,47,.35)',big?4:2);}
    g.restore();
  }
  function cup(g,img,x,y,size,angle,tilt=0) {
    if(!img||!img.naturalWidth)return;
    const idx=Math.round(clamp(angle)*29),cell=img.naturalWidth/6;
    transformed(g,x,y,tilt,1,1,()=>g.drawImage(img,(idx%6)*cell,Math.floor(idx/6)*cell,cell,cell,-size/2,-size/2,size,size));
  }
  function trail(g,x,y,x2,y2,t,c) {
    g.save();g.setLineDash([10,14]);g.lineDashOffset=-t*62;line(g,x,y,x2,y2,c,4);g.restore();
  }
  function tag(g,label,x,y,w,r,p,accent) {
    transformed(g,x,y,r,mix(.72,1,p),p,()=>{
      shadow(g,()=>rect(g,0,0,w,103,accent?orange:cream,9));
      ellipse(g,21,52,7,7,ink);txt(g,label,w*.55,53,54,ink,{mono:true,weight:900,align:'center'});
    });
  }
  function ticket(g,sc,i,x,y,rot,p,t){
    transformed(g,x,y,rot,1,p,()=>{
      shadow(g,()=>toothed(g,0,0,822,238,i?yellow:'#fffdf1'));
      rect(g,0,0,13,229,i?orange:ink);txt(g,sc.rowLabels[i],34,44,34,ink);
      txt(g,sc.product,33,108,49);txt(g,sc.sku+'   /   '+sc.spec,35,174,31,ink,{mono:true});
      g.save();g.setLineDash([9,10]);line(g,405,22,405,210,'#7e826b',2);g.restore();
      txt(g,sc.currency,441,120,48);txt(g,sc.prices[i],487,113,91,ink,{mono:true});
      barcode(g,489,173,267,27,ink);
    });
  }
  function stamp(g,s,x,y,w,t,a,rotation=-.08){
    const u=ramp(t,a,.28);if(!u)return;
    transformed(g,x,y,rotation,1+.72*(1-u),u,()=>{
      rect(g,-w/2,-48,w,96,orange,8);g.strokeStyle=ink;g.lineWidth=3;g.strokeRect(-w/2+8,-40,w-16,80);
      txt(g,s,0,-1,50,ink,{align:'center',weight:900});});
  }
  function product(g,sc,t,H,img){
    const enter=ramp(t,0,.85),spin=ease(t,.20,3.45);
    const photo=H.$('s'+H.i+'_photo');
    if(photo&&photo.naturalWidth){g.save();g.globalAlpha=.12;H.drawFrame(g,photo,-65,-65,1210,2050);g.restore();}
    const cx=551,cy=890;ellipse(g,cx,cy,390*enter,390*enter,orange);orbit(g,cx,cy,422,t);
    // The highlight travels on the studio turntable while the body comes into view.
    ellipse(g,540,1150,258*enter,31,'rgba(44,31,19,.22)');
    cup(g,img,534+22*Math.sin(t),881-65*(1-enter)+10*Math.sin(t*1.55),820*mix(.75,1,enter),spin,-.105+.11*spin);
    headline(g,sc,t,true);
    const a=ramp(t,1.04,.38),b=ramp(t,2.36,.4);
    tag(g,sc.prices[0],119-140*(1-a),1080,283,-.12,a,false);
    tag(g,sc.prices[1],625+145*(1-b),1100,283,.085,b,true);
    line(g,84,1317,995,1317,'#96a892');txt(g,sc.product,86,1370,46,cream);
    txt(g,sc.sku+'  /  '+sc.spec,985,1370,35,light,{mono:true,align:'right'});
  }
  function tickets(g,sc,t,H,img) {
    paper(g,t);headline(g,sc,t,false);
    const a=ramp(t,.18,.72),b=ramp(t,1.76,.65),compare=ease(t,3.22,.61);
    cup(g,img,840,401,260,.18+.58*ease(t,.5,4.8),.10);
    ticket(g,sc,0,mix(-680,127,a),mix(654,608,compare),mix(-.13,-.048,a),a,t);
    ticket(g,sc,1,mix(990,108,b),mix(900,912,compare),mix(.16,.038,b),b,t);
    const mark=ramp(t,3.8,.62);trail(g,751,802,751,918,t,'#b55d35');
    transformed(g,415,1263,-.05,mix(.75,1,mark),mark,()=>{rect(g,-305,-62,590,124,ink,6);
      txt(g,sc.delta,-8,1,65,yellow,{align:'center'});});
  }
  function evidence(g,sc,t,H) {
    headline(g,sc,t,true);
    const pop=ramp(t,.20,.62), f=H.frame(sc,t);
    // Follow the physical report down the page, then ease back to its two source rows.
    transformed(g,78+12*Math.sin(t*1.15),639+105*(1-pop)-18*t,
      .012*Math.sin(t*1.4),1+.008*t,pop,()=>{
      shadow(g,()=>rect(g,0,0,920,604,cream,18));rect(g,0,0,920,73,yellow,14);
      ellipse(g,33,36,9,9,ink);ellipse(g,63,36,9,9,orange);
      txt(g,sc.win,100,36,32);txt(g,sc.file,883,36,29,ink,{align:'right'});
      g.save();g.beginPath();g.rect(12,83,896,506);g.clip();
      if(f){const zoom=1+.055*ease(t,2.0,1.9);g.drawImage(f,12-(zoom-1)*413,83-(zoom-1)*265,896*zoom,506*zoom);}
      else txt(g,sc.pending,460,338,50,ink,{align:'center'});
      g.restore();
      const scan=ramp(t,.62,1.3)*(1-ease(t,3.15,.42));
      g.save();g.globalAlpha=scan;const scanY=110+415*ease(t,.61,2.32);
      const grad=g.createLinearGradient(0,scanY-55,0,scanY);grad.addColorStop(0,'rgba(18,120,88,0)');grad.addColorStop(1,'rgba(18,120,88,.26)');rect(g,12,scanY-55,896,55,grad);line(g,12,scanY,908,scanY,'#14734d',5);g.restore();
    });
    const reveal=ramp(t,2.92,.5);
    transformed(g,94,1260,0,1,reveal,()=>{pill(g,sc.rowLabels[0],0,0,273,cream,ink);pill(g,sc.rowLabels[1],289,0,273,cream,ink);});
    transformed(g,97,1385,0,1,ramp(t,3.85,.5),()=>{rect(g,0,-15,17,30,orange);txt(g,sc.status,36,0,40,yellow);});
  }
  function normalize(g,sc,t,H){
    paper(g,t);headline(g,sc,t,false);
    const convert=H.at(sc,'写法')??1.0,match=H.at(sc,'货号')??3.1;
    const q=ease(t,convert,.68);
    for(let i=0;i<2;i++){
      const y=588+i*234,a=ramp(t,.15+i*.28,.5);
      const flutter=Math.sin(t*1.9+i*2.85);
      transformed(g,79+(1-a)*(i?340:-320)+15*flutter,y+9*Math.cos(t*1.68+i*2.4),
        .021*flutter,1,a,()=>{
        shadow(g,()=>rect(g,0,0,920,195,'#fffdf4',14));
        rect(g,0,0,16,195,i?orange:ink,6);txt(g,sc.rowLabels[i],38,40,32);
        txt(g,sc.raw[i],38,122,i?77:58,'#5d6f60',{mono:true});
        const reach=ramp(t,convert+i*.23,.55);
        line(g,395,111,395+100*reach,111,ink,4);
        if(reach>.02){line(g,495,111,472,93,ink,4);line(g,495,111,472,129,ink,4);}
        g.save();g.beginPath();g.rect(531,58,360*q,115);g.clip();
        rect(g,532,64,347,100,i?yellow:ink,8);txt(g,sc.values[i],700,116,81,i?ink:cream,{mono:true,align:'center'});g.restore();
      });
    }
    // A reader crosses both normalized records after the digits have settled.
    const reading=ease(t,1.46,.5);
    const readerX=94+882*(.5-.5*Math.cos((t-1.46)*2.04));
    g.save();g.globalAlpha=reading*.74;
    const band=g.createLinearGradient(readerX-61,0,readerX+4,0);
    band.addColorStop(0,'rgba(48,137,96,0)');band.addColorStop(1,'rgba(48,137,96,.34)');
    rect(g,readerX-61,589,64,437,band);line(g,readerX,589,readerX,1026,'#309066',4);
    g.restore();
    const pull=ease(t,match-.72,.70);
    transformed(g,mix(76,286,pull),1110,0,1,ramp(t,1.42,.4),()=>pill(g,sc.store,0,0,235,ink,cream));
    transformed(g,mix(742,531,pull),1110,0,1,ramp(t,1.66,.4),()=>pill(g,sc.sku,0,0,237,ink,cream));
    stamp(g,sc.problem,531,1330,478,t,Math.min(H.dur-1.25,match+.43));
  }
  function archive(g,sc,t,H) {
    headline(g,sc,t,true);
    const folderY=952;const open=ramp(t,.08,.68);
    rect(g,96,folderY-145,349,125,orange,22);rect(g,96,folderY-92,883,394,orange,22);
    const settle=ease(t,3.22,.75);
    for(let i=0;i<2;i++){
      const enter=ramp(t,.34+i*.58,.7);
      transformed(g,140+42*i+(i?1:-1)*490*(1-enter),570+i*174+61*settle,.01+(i?1:-1)*.025*enter,1,enter,()=>{
        shadow(g,()=>toothed(g,0,0,778,184,i?yellow:cream));
        txt(g,sc.rows[i],35,46,31);txt(g,sc.sku,36,119,44,ink,{mono:true});
        txt(g,sc.prices[i],737,94,76,ink,{align:'right',mono:true});
      });
    }
    const top=1019-29*open+12*Math.sin(t*1.1);
    g.beginPath();g.moveTo(83,top);g.quadraticCurveTo(84,top-13,112,top-13);g.lineTo(425,top-13);g.lineTo(492,top+26);g.lineTo(1008,top+26);g.lineTo(970,1267);g.lineTo(109,1267);g.closePath();color(g,'#e6bb77');g.fill();
    txt(g,sc.folder,150,top+112,80);barcode(g,156,top+175,178,31,ink);
    stamp(g,sc.status,731,top+142,337,t,H.at(sc,'冲突')??1.6,.07);
    const k=H.at(sc,'原单')??3.28;transformed(g,83,1345,0,1,ramp(t,k-.2,.45),()=>{rect(g,0,-47,480,94,cream,6);txt(g,sc.instruction,33,0,51);line(g,321,0,433,0,ink,4);line(g,433,0,410,-18,ink,4);line(g,433,0,410,18,ink,4);});
  }
  function claim(g,sc,t,H,img){
    paper(g,t);headline(g,sc,t,false);
    const a=ramp(t,.18,.8),b=ramp(t,1.05,.6);
    ellipse(g,650,814,300*a,300*a,orange);orbit(g,650,814,321,t,false);
    cup(g,img,640+19*Math.sin(t),813,604*a,1-ease(t,.2,4.6),.08*Math.sin(t));
    transformed(g,146,692,-.1,1,b,()=>{shadow(g,()=>toothed(g,0,0,300,182,yellow));txt(g,sc.slip,27,66,48);barcode(g,27,120,225,26,ink);});
  }
  const paints={product,tickets,evidence,normalize,archive,claim};
  const beats={product:[.95,2.3,3.45],tickets:[1.65,3.17,4.78,5.85],evidence:[1.2,2.75,4.32],normalize:[1.04,2.54,4.02],archive:[1.13,2.58,4.12,5.42],claim:[.9,2.15,3.58,4.64]};
  function scene(name) {
    return {bg:BG.base[1],build(sc,id,H){
      const control=name==='claim'?K.ctaBlock(id+'claim',sc,H,{x:86,y:1083,w:534}).html:'';
      const loadCup=['product','tickets','claim'].includes(name)?'<img hidden id="'+id+'cup" src="'+art+'">':'';
      const photo=name==='product'?'<img hidden id="'+id+'photo" src="'+H.img(sc.image)+'">':'';
      return K.layers(id,'<canvas id="'+id+'paint" width="1080" height="1920"></canvas>'+control+loadCup+photo);
    },anim(sc,id,t,H){
      K.frame(id,t,H,BG,{push:.012,seed:8,beats:beats[name],beat:.027});
      const g=H.$(id+'paint').getContext('2d');g.clearRect(0,0,1080,1920);
      paints[name](g,sc,t,H,H.$(id+'cup'));
      if(name==='claim')K.ctaBlock(id+'claim',sc,H,{x:86,y:1083,w:534}).anim(t,{show:.6,follow:1.64,type:2.55,send:3.66});
    },sfx:()=>beats[name].slice(0,3).map((b,i)=>[b,i===2?'ding':'tick'])};
  }
  window.VISUALS=Object.fromEntries(Object.keys(paints).map(name=>[name,scene(name)]));
  window.VISUALS.outro=K.outro(BG);
})();
