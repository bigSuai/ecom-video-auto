(() => {
  const {box,label,path,at,live,circle,progress,scene}=window.STORY;
  const bg='#273548', gold='#ffdb80', blue='#abcfff', cream='#f9efda';
  function parcel(g,x,y,i){
    at(g,x,y,-.04,()=>{box(g,0,0,142,89,i?blue:gold,3);box(g,58,0,20,88,'#e7b37c');box(g,10,51,41,22,cream);});
  }
  function belt(g,t,split){
    path(g,[[83,772],[409,772],[821,540]],blue,40);
    path(g,[[412,772],[820,1007]],gold,40);
    for(let i=0;i<8;i++){
      const p=(i/8+t*.18)%1, right=Math.max(0,(p-.39)/.61);
      const x=88+p*737, y=770+(i%2?1:-1)*234*right*split;
      parcel(g,x-52,y-82,i%2);
    }
    label(g,'店铺甲',746,440,59,blue,250);label(g,'店铺乙',747,1082,59,gold,250);
  }
  function draw(g,s,t,H,stage){
    label(g,'备货分拣线   /   DEMO-CUP-01',62,121,34,blue);
    if(stage==='live'){
      label(g,'逐字段读回',62,297,101,cream);
      live(g,s,t,H,45,508,990,gold,bg,'演示后台连续填写');
      label(g,'停在提交确认前',66,1263,72,gold);
    }else if(stage==='align'){
      label(g,'货号相同，按店核对',62,315,80,cream);
      ['标题','类目','规格','价格','库存'].forEach((v,i)=>{
        const y=512+i*145,p=progress(t,.22+i*.47,.45);box(g,89,y,881,105,i%2?'#344b64':'#3d4a59',10);
        label(g,v,119,y+51,54,cream);box(g,408,y+38,456*p,24,i%2?blue:gold,8);circle(g,411+447*p,y+50,18,cream);
      });
    }else if(stage==='claim'){
      label(g,'领取上架助手',65,293,96,cream);
      for(let i=0;i<5;i++) parcel(g,60+((t*83+i*222)%967),660,i%2);
    }else{
      label(g,stage==='compare'?'一只杯子，分两条线':'两店各留一条',62,301,83,cream);
      belt(g,t,.6+.4*progress(t,.2,1.1));
      if(stage==='resolution')label(g,'队列阶段    已准备',80,1267,68,gold);
    }
  }
  for(const st of ['compare','live','align','resolution','claim'])scene('listing-queue',st,{bg,beats:[.48,1.6,3.06,4.63]},draw);
})();
