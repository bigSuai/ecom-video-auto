(() => {
  const {box,label,path,live,measured,progress,scene}=window.STORY;
  const navy='#192d42', sky='#a9cee2', paper='#fff4d8', red='#af422f';
  function receipt(g,x,y,w,rows,t){
    box(g,x-12,y-16,w+24,34,navy,12);
    g.save();g.beginPath();g.rect(x-2,y,w+4,rows.length*99+70);g.clip();
    g.translate(0,-(1-progress(t,0,.95))*(rows.length*99+34));
    box(g,x,y,w,rows.length*99+50,paper);
    for(let i=0;i<w-10;i+=26) path(g,[[x+i,y+rows.length*99+50],[x+i+13,y+rows.length*99+65],[x+i+26,y+rows.length*99+50]],paper,0,true);
    rows.forEach(([k,v],i)=>{
      const baseline=y+63+i*99;
      label(g,k,x+30,baseline,42,navy,w*.43);
      label(g,v,x+w*.53,baseline,59,k.includes('退款')?red:navy,w*.42);
      box(g,x+26,baseline+36,w-52,2,'#c7baa4');
    });
    g.restore();
  }
  function draw(g,s,t,H,stage){
    const open=stage==='hook', mid=stage==='live';
    for(let i=0;i<18;i++) box(g,0,70*i+((t*18)%70),1080,2,'#9cc1d7');
    label(g,'三店合账  /  CNY',55,119,37,navy);
    const lift=progress(t,0,1.2);
    if(open){
      label(g,'到账之后，',49,237,104,navy); label(g,'退款去了哪？',49,358,102,navy);
      receipt(g,130,423+44*lift,810,[['实付合计',s.values[0]],['退款',s.values[1]]],t);
      live(g,s,t,H,58,852,964,navy,paper,'翻开本次订单账本'); measured(g,s,t,65,1460,navy);
    }else if(mid){
      receipt(g,145,235,790,[['实付合计',s.values[0]],['退款合计',s.values[1]],['净销售额',s.values[2]]],t);
      live(g,s,t,H,48,747,984,navy,paper,'逐店读取报表');
    }else if(stage==='compare'){
      label(g,'多算的那一笔',65,292,91,navy);
      receipt(g,170,487+62*lift,740,[['订单收款',s.values[0]],['退回顾客',s.values[1]]],t);
      const y=1000+36*Math.sin(t*1.7);path(g,[[875,750],[950,750],[950,y],[800,y]],red,12);
      const refund=progress(t,.95,1.65);
      box(g,625-468*refund,705+(y-705)*refund,227,89,'#f6cfad',8);
      label(g,'−¥20',640-468*refund,748+(y-705)*refund,63,red,200);
      label(g,'原路退回',411,y+49,76,red,376);
    }else if(stage==='align'){
      label(g,'按币种归集',62,288,94,navy);
      receipt(g,92,505+52*lift,895,[['实付',s.values[0]],['退款',s.values[1]],['净销售额',s.values[2]]],t);
      const y=1000+42*Math.sin(t*1.6);box(g,174,y,737,159,'#ffe0a0',8);
      label(g,'单列费用   广告费 ¥12',202,y+76,53,navy);
    }else{
      label(g,stage==='claim'?'领取复盘助手':'撕下结算联',62,280,92,navy);
      receipt(g,103,452+55*lift,873,[['实付减退款','230 − 20'],['净销售额','¥210']],t);
      if(stage==='resolution') label(g,'¥210',113,1090+17*Math.sin(t*2),191,navy);
    }
  }
  for(const st of ['hook','compare','live','align','resolution','claim'])scene('net-sales',st,{bg:sky,beats:[.55,1.6,3.05,4.75]},draw);
})();
