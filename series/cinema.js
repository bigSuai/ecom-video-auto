/* Spatial openings, match cuts into actual operations, and a physical payoff for each topic. */
(() => {
  const {box,label,path,circle,at,progress:P}=window.STORY, K=window.KIT;
  const paper='#fff1cf', dark='#10252c', hot='#ff754b', mint='#93eed5';
  const guide={
    B:['一只杯子','两种售价','跟回原表','两行都要留','价格冲突','同店同货号','s2-sheet-errors.jpg','#123b35','#ffd27c'],
    D:['三家店收款','账上剩多少？','逐店合账','净销售额','¥210','实付减退款','s8-reports.jpg','#142f4a','#ffcf72'],
    F:['工单已处理','顾客收到了吗？','追踪回复','物流查询','仍待回复','C1 · 已超时','s6-cs-morning.jpg','#282440','#ffa5a3'],
    C:['同一个广告词','两把时间尺','对齐归因窗口','各算各的回报','6  /  4','七日点击与一日点击','s5-calendar.jpg','#102d44','#64e4dc'],
    G:['两个标价','哪组能比？','校准快照','本店低了','¥1.10','规格 · 价格类型 · 币种','s1-price-check.jpg','#243830','#ffc596'],
    A:['万件待上架','怎么分给两家店？','按店分拣','每店各留一条','已准备','提交前人工确认','s4-night-desk.jpg','#162a3d','#ffca72'],
    E:['一只杯子','四份素材初稿','挑出主图','选中的主图','已导出','主图 · 详情 · 图文 · 视频','s3-studio.jpg','#452934','#ffad7e']
  };
  const sprite=new URL('cup-turntable.webp',document.currentScript.src).href;
  function pose(g,x,y,r,scale,fn){at(g,x,y,r,()=>{g.scale(scale,scale);fn()});}
  function ellipse(g,x,y,rx,ry,fill){g.beginPath();g.ellipse(x,y,rx,ry,0,0,Math.PI*2);g.fillStyle=fill;g.fill();}
  function title(g,l,x,y,size,color,limit=950){g.save();g.shadowColor='#0009';g.shadowBlur=15;label(g,l,x,y,size,color,limit,900);g.restore();}
  function ticket(g,x,y,r,scale,tag,value,color){
    pose(g,x,y,r,scale,()=>{box(g,-125,-66,256,138,'#0006',9);box(g,-132,-74,256,135,color,9);
      circle(g,-112,-50,5,dark);label(g,tag,-93,-46,24,dark,194);
      label(g,value,-108,13,49,dark,219);for(let k=0;k<15;k++)box(g,-103+k*12,44,3+(k%3),9,dark);});
  }
  function cup(g,im,x,y,w,t){if(!im?.naturalWidth)return;const n=Math.floor(t*7)%30,s=im.naturalWidth/6;
    g.drawImage(im,(n%6)*s,Math.floor(n/6)*s,s,s,x-w/2,y-w/2,w,w);}
  function glow(g,x,y,r,tint){const grad=g.createRadialGradient(x,y,1,x,y,r);grad.addColorStop(0,tint);grad.addColorStop(1,'transparent');box(g,x-r,y-r,2*r,2*r,grad);}
  function backdrop(g,img,t,d){
    box(g,0,0,1080,1920,d[7]);if(img?.naturalWidth){
      const k=Math.max(1080/img.naturalWidth,1920/img.naturalHeight)*(1.09+.014*Math.sin(t*.72));
      const w=img.naturalWidth*k,h=img.naturalHeight*k;g.save();g.globalAlpha=.61;
      g.drawImage(img,(1080-w)/2+18*Math.sin(t*.6),(1920-h)/2+22*Math.cos(t*.48),w,h);g.restore();}
    const wash=g.createLinearGradient(0,0,0,1920);wash.addColorStop(0,'#0e1726c7');wash.addColorStop(.40,'#12182352');wash.addColorStop(.76,'#0b1424d4');wash.addColorStop(1,'#081321');box(g,0,0,1080,1920,wash);
    glow(g,248+62*Math.sin(t*.56),678,560,d[8]+'33');
  }
  function porcelain(g,t,p,im){
    for(let i=0;i<10;i++){const z=((i*.149+t*.12)%1),x=95+(i%5)*220;g.save();g.globalAlpha=.15+.25*z;
      ticket(g,x+(i%2?1:-1)*z*54,210+z*300,-.12+i*.018,.34+z*.43,'商品表',i%2?'20.00':'19.90',paper);g.restore();}
    ellipse(g,525,522,277,42,'#06181099');ellipse(g,525,507,294,42,'#eacfa3');
    cup(g,im,523,350,468,t);
    ticket(g,203-56*p,379+18*Math.sin(t*1.8),-.17,.9,'第 2 行','¥19.90',paper);
    ticket(g,826+45*p,455-16*Math.sin(t*1.5),.14,.91,'第 3 行','¥20.00','#ffd37b');
  }
  function accounts(g,t,p){
    for(let i=0;i<3;i++){
      const x=167+i*372, c=[mint,'#a2c8ff','#ffce7a'][i],y=202+Math.sin(t+i)*8;
      box(g,x-96,y,194,99,'#203d47',9);box(g,x-104,y-11,210,30,c,5);label(g,'店 '+(i+1),x-50,y+56,39,paper,140);
      for(let k=0;k<3;k++){const u=(t*.42+i*.15+k/3)%1;
        ticket(g,x+(538-x)*u,y+129+u*178,(-.15+i*.15)*(1-u),.42+.10*u,'流水','实付',c);}
    }
    box(g,342,499,399,46,'#1b2532',12);const lift=P(t,.4,.9);
    box(g,379,531,325,80+73*lift,paper);label(g,'实付  ¥230',403,571,43,dark);
    if(lift>.45)label(g,'退款  −¥20',403,630,43,'#b33f30');
  }
  function dispatcher(g,t,p){
    for(let i=0;i<4;i++){
      const incoming=(t*.20+i*.25)%1;const x=77+incoming*155,y=200+i*88;
      box(g,x,y,390,68,i===1?'#fde8cd':'#233c44',24);label(g,['库存咨询','物流在哪里？','本地处理','待查发送记录'][i],x+26,y+34,34,i===1?dark:paper,355);
    }
    const a=t*1.3;circle(g,831,307,107,'#ffd594');circle(g,831,307,87,'#313244');
    path(g,[[831,245],[831,307],[831+48*Math.cos(a),307+47*Math.sin(a)]],paper,7);
    const x=550+88*Math.sin(t*1.75);
    pose(g,x,500,-.13,1,()=>{path(g,[[0,10],[175,-51],[118,73],[80,39],[51,74],[47,32]],hot,0,true);path(g,[[49,33],[146,-26],[80,39]],dark,5);});
    label(g,'等待回复',701,520,49,'#ffc0af',326);
  }
  function attribution(g,t,p){
    for(let i=6;i>=0;i--){const x=95+i*120,y=246-i*13;
      pose(g,x,y,-.07+i*.012,.92,()=>{box(g,0,0,153,178,'#06182099',8);box(g,0,-10,150,166,paper,8);box(g,0,-10,150,43,'#4fb7b3',7);label(g,'DAY',16,12,23,dark);label(g,String(i+1),23,96,80,dark);});}
    const sweep=.35+.65*P(t,.15,1.55);
    box(g,86,487,889*sweep,44,mint,20);box(g,86,562,127*sweep,44,'#ffcc70',20);
    circle(g,86+889*sweep,509,17,paper);circle(g,86+127*sweep,584,17,paper);
    label(g,'7 日',842,449,38,paper);label(g,'1 日',234,584,37,paper);
  }
  function scales(g,t,p){
    const angle=-.12+.19*P(t,.2,1.25)+.026*Math.sin(t*2.1);
    path(g,[[542,324],[459,587],[627,587]],'#bbcabb',7,true);
    pose(g,540,334,angle,1,()=>{box(g,-360,-9,720,18,paper,9);
      for(const [i,x] of [-315,315].entries()){
        path(g,[[x,0],[x-101,202],[x+101,202],[x,0]],'#d3cbb4',4);
        ellipse(g,x,201,129,31,i?'#fc9a72':mint);
        ticket(g,x,132,-angle,.73,i?'竞品':'本店',i?'¥21.00':'¥19.90',i?'#ffceaa':paper);
      }});circle(g,540,334,21,hot);
  }
  function warehouse(g,t,p){
    for(let lane=-4;lane<=4;lane++)for(let i=0;i<10;i++){
      const z=(i/10+t*.20+Math.abs(lane)*.037)%1,y=167+480*z*z,x=540+lane*(20+z*166);
      const w=24+103*z;box(g,x-w/2,y,w,w*.59,lane%2?'#b7c8dd':'#e1b77d',4);
      box(g,x-w*.12,y,w*.2,w*.59,'#ffe5ac');}
    label(g,'规模场景示意',64,193,33,paper);title(g,'10,000',55,313,153,'#ffcf71',730);
  }
  function studio(g,t,p,im){
    for(let i=0;i<4;i++){const u=(i-1.5),spread=.4+.6*P(t,0,1.3);
      pose(g,540+u*232*spread,400+Math.abs(u)*32+12*Math.sin(t+i),u*.16,.94,()=>{
        box(g,-108,-147,223,289,'#0007',5);box(g,-114,-156,222,282,paper,5);
        box(g,-103,-144,199,190,['#dd975a','#c8c993','#baaccb','#89b6c1'][i]);cup(g,im,-4,-49,185,t+i);
        label(g,['主图','详情','图文','短视频'][i],-87,83,44,dark,178);});}
    for(let k=0;k<2;k++){const x=k?915:124;path(g,[[x,126],[x-80,258],[x+80,258]],'#fff4c318',0,true);}
  }
  const objects={A:warehouse,B:porcelain,C:attribution,D:accounts,E:studio,F:dispatcher,G:scales};
  function opening(g,s,t,H,m,im,accent,p){
    const observed=m==='B'?'回查原表第 2、3 行的价格':s.hook_status;
    const screen=(x,y,w,caption,zoom=1+.25*p)=>monitor(g,s,t,H,x,y,w,
      t>=s.hook_result_at?'本机实录　/　'+observed:caption,accent,zoom);
    const stage=(x,y,z)=>pose(g,x,y,0,z,()=>{g.translate(-540,0);objects[m](g,t,p,im);});
    const w=881+112*p;
    if(m==='A'){
      stage(540,2,1.19-.12*p);
      title(g,'分给两家店',76,700,83,paper);
      screen((1080-w)/2,880-34*p,w,'本机实操　/　填写商品 → 逐字段读回');
    }else if(m==='B'){
      box(g,57,114,350,52,'#edce95',4);label(g,'商品档案　000087',78,141,32,dark,315);
      title(g,'一只杯子，两张价签',61,244,90,paper);
      stage(548,240-84*p,1.13-.13*p);
      screen((1080-w)/2,933-86*p,w,'打开原始资料　/　查同一货号');
    }else if(m==='C'){
      title(g,'同一个广告词',60,162,87,paper);title(g,'该看哪几天？',59,274,100,accent);
      screen((1080-w)/2,428-22*p,w,'本机实操　/　打开投放明细');
      stage(543,936-25*p,.80);
    }else if(m==='D'){
      title(g,'三店收款',64,150,92,paper);title(g,'¥230',598,153,121,accent,407);
      stage(540,131,1.01);
      box(g,72,813,937,12,'#bdd8cb',4);
      screen((1080-w)/2,918-31*p,w,'从订单到账本　/　实付、退款、净额');
    }else if(m==='F'){
      box(g,59,95,413,73,'#ffeada',33);label(g,'物流到哪里了？',84,133,45,dark,360);
      title(g,'回复发出了吗？',62,274,98,paper);
      stage(541,174,1.04-.07*p);
      const y=889-60*p;box(g,26,y-82,1028,w*.63+116,'#664c69',31);
      screen((1080-w)/2,y,w,'售后值班室　/　打开本次工单');
    }else if(m==='G'){
      title(g,'两个价格，能比吗？',56,193,93,paper);
      screen((1080-w)/2,397-13*p,w,'本机实操　/　从商品快照核对规格');
      stage(545,911,.83);
    }else{
      for(let i=0;i<14;i++){const x=(i*94+t*56)%1190-83;box(g,x,109,45,15,'#d0b7a0',3);}
      title(g,'一只杯子的选片台',58,248,93,paper);
      stage(537,205,1.16-.14*p);
      screen((1080-w)/2,933-72*p,w,'实操选片台　/　打开当次生成的主图');
    }
  }
  function finish(g,m,t,im) {
    const p=P(t,.35,1.4),swing=Math.sin(t*1.5);
    if(m==='D'){
      const cx=198+70*p;ticket(g,cx,306,-.12,.97,'实付','¥230',paper);
      ticket(g,906-240*p,310+157*p,.13,.83,'退款','−¥20','#f8a98b');
      path(g,[[cx+135,314],[516,314],[516,493],[618,493]],mint,7);
      label(g,'归入净销售额',236,591+10*swing,63,paper);
    }else if(m==='F'){
      box(g,120,224,831,307,'#233a40',18);label(g,'C1　物流查询',165,286,66,paper);
      box(g,167,362,625,13,'#51615d');box(g,167,363,440*p,12,hot);
      pose(g,725,455,-.12+.09*(1-p),1.22-.22*p,()=>{box(g,-140,-53,280,106,hot,8);label(g,'逾期未回复',-121,0,44,dark,241);});
    }else if(m==='C'){
      for(const [i,row] of [['7 日点击','6',mint],['1 日点击','4','#ffce74']].entries()){
        const yy=230+167*i;label(g,row[0],85,yy,50,paper);box(g,358,yy-22,(i?340:505)*(.08+.92*p),43,row[2],12);
        label(g,row[1],906,yy,75,row[2]);}
      label(g,'各自窗口内的 ROAS',181,593+8*swing,56,paper);
    }else if(m==='G'){
      const x=122,y=320,w=818;box(g,x,y,w,16,paper);
      for(let i=0;i<=25;i++)box(g,x+w*i/25,y+15,3,i%5?21:45,paper);
      const a=260+116*p,b=765-97*p;for(const [i,n] of [a,b].entries()){
        path(g,[[n-24,y-29],[n+24,y-29],[n,y]],i?hot:mint,0,true);label(g,i?'¥21.00':'¥19.90',n-98,y-86,57,i?'#ffb591':mint);}
      path(g,[[a,429],[a,470],[b,470],[b,429]],mint,5);label(g,'差 ¥1.10',400,565,74,paper);
    }else if(m==='A'){
      for(let i=0;i<2;i++)ticket(g,516+(i?1:-1)*(70+218*p),360+15*swing,i?.1:-.1,1.25,'DEMO-CUP-01',i?'店铺乙':'店铺甲',i?'#9cdef3':'#f2ca81');
      label(g,'已准备　→　等待确认',203,609,62,paper,743);
    }else if(m==='E'){
      box(g,494,338,419,197,'#d09574',12);ticket(g,224+397*p,241+107*p,-.18+.18*p,1.35,'已选素材','主图',paper);
      cup(g,im,618,318,108,t);box(g,482,478,458,100,'#ffb88c',14);label(g,'导出目录',526,524,49,dark);
    }
  }
  function monitor(g,s,t,H,x,y,w,titleText,accent,zoom){
    const frame=H.frame(s,t);if(!frame)throw Error('实操段缺少源录像');
    const h=w*(s.slot==='mid'?.76:.63);
    g.save();g.shadowColor='#000b';g.shadowBlur=45;g.shadowOffsetY=14;
    box(g,x-6,y-58,w+12,h+68,'#111d24',12);g.restore();
    box(g,x-6,y-58,w+12,56,'#172c32',11);
    circle(g,x+24,y-31,7,accent);label(g,titleText,x+46,y-31,30,paper,w-60);
    g.save();g.beginPath();g.rect(x,y,w,h);g.clip();
    const track=s.pointer_focus||[], n=Math.min(Math.max(0,track.length-1),Math.floor(t*10));
    const a=track[n]||[.44,.42],b=track[n+1]||a,f=t*10%1;
    const cx=a[0]+(b[0]-a[0])*f,cy=a[1]+(b[1]-a[1])*f;
    const sh=frame.height/zoom,sw=sh*w/h;
    const sx=Math.min(frame.width-sw,Math.max(0,cx*frame.width-sw*.44));
    const sy=Math.min(frame.height-sh,Math.max(0,cy*frame.height-sh*.48));
    g.drawImage(frame,sx,sy,sw,sh,x,y,w,h);
    g.restore();
  }
  function register(sid,m,stage,name){
    const d=guide[m],accent=d[8],hasCup=m==='B'||m==='E';
    window.VISUALS[name]={bg:d[7],build(s,id,H){
      const media='<img hidden id="'+id+'location" src="'+H.img(d[6])+'">'+(hasCup?'<img hidden id="'+id+'cup" src="'+sprite+'">':'');
      return K.layers(id,'<canvas width="1080" height="1920" id="'+id+'cine"></canvas>'+media);},
    anim(s,id,t,H){
      const g=H.$(id+'cine').getContext('2d'),im=H.$(id+'cup');
      box(g,0,0,1080,1920,d[7]);g.save();
      const pace={A:1.22,B:1.43,C:1.36,D:1.57,E:1.48,F:1.32,G:1.52}[m];
      const pulse=Math.max(0,Math.sin(2*Math.PI*t/pace))**6;
      const dolly=1.007+.024*Math.sin(t*1.85)+.036*pulse;
      g.translate(540+11*Math.sin(t*1.76),860+11*Math.cos(t*1.62));
      g.scale(dolly,dolly);g.translate(-540,-860);
      backdrop(g,H.$(id+'location'),t,d);
      const push=P(t,.8,1.28),wave=Math.sin(t*1.45);
      if(stage==='hook'){
        opening(g,s,t,H,m,im,accent,push);
      }else if(stage==='live'){
        const actions={A:['填写商品','逐字段读回'],B:['检索价格冲突','导出原始记录'],C:['选择归因窗口','导出投放记录'],D:['打开合计','导出净销售记录'],E:['选定主图','导出文件'],F:['找到物流工单','导出回复凭据'],G:['打开竞品对照','导出可比快照']};
        const reveal=P(t,H.dur*.52,.45),[before,after]=actions[m];
        label(g,'本次运行   /   '+d[2],66,194,42,accent);
        title(g,reveal>.55?after:before,58,347,105,paper);
        const w=953+53*P(t,.15,.85), y=523-36*P(t,1.1,.9);
        monitor(g,s,t,H,(1080-w)/2,y,w,'本地连续录屏　/　虚构业务样例',accent,1+.37*P(t,.65,1.16)-.14*P(t,H.dur-1.3,.8));
        const px=96+(826*Math.min(1,t/H.dur));box(g,93,1305,832,5,'#c1c9c166');box(g,93,1302,Math.max(2,px-93),10,accent,4);circle(g,px,1307,12,paper);
        label(g,before,72,1382,48,paper,445);label(g,after,545,1382,48,reveal>.3?accent:'#a7b6b5',492);
      }else{
        const payoff=stage==='resolution', impact=P(t,.35,.8);
        label(g,payoff?'本次答案':'问题拆解',70,148,38,accent);
        title(g,payoff?d[3]:s.head[0],60,297,100,paper);
        title(g,payoff?d[4]:s.head[1],60,427,payoff?135:100,accent);
        g.save();g.translate(540,355+22*wave);const z=.86+.23*impact;g.scale(z,z);g.translate(-540,0);
        if(payoff)finish(g,m,t,im);else objects[m](g,t,impact,im);g.restore();
        const lineY=1104+28*(1-impact);box(g,68,lineY,940,4,accent);
        const text=payoff?d[5]:({A:'同一货号　→　两家店各一条',B:'同一家店　→　同一货号',C:'点击发生　→　结算窗口',D:'三店收款　→　退回一笔',E:'一份资料　→　四类初稿',F:'店内处理　→　核对发送凭据',G:'匹配同款　→　再读价差'}[m]);
        title(g,text,72,lineY+98,58,paper,924);
        if(payoff && m==='D')label(g,'¥230   −   ¥20   =   ¥210',71,lineY+209,64,accent);
      }
      g.restore();
    },sfx:()=>[[.32,'tick'],[1.13,'pop'],[2.65,'ding']]};
  }
  window.installCinema=(sid,module,scenes)=>{
    const editions={A:'listing-queue',B:'ceramic-price',C:'ad-window',D:'net-sales',E:'media-drafts',F:'service-reply',G:'comparable-price'};
    if(editions[module]!==sid)return;
    for(const [stage,i] of [['hook',0],['compare',1],['live',2],['resolution',4]]){
      if(module==='B'&&['compare','resolution'].includes(stage))continue;
      register(sid,module,stage,scenes[i]);
    }
  };
})();
