/* The warehouse-wide opening belongs to the listing queue story. */
(() => {
  const K = window.KIT;
  const sans = '"Microsoft YaHei", "Noto Sans CJK SC", sans-serif';
  function rectangle(ctx, x, y, w, h, fill, radius = 0) {
    ctx.beginPath(); ctx.roundRect(x, y, w, h, radius);
    ctx.fillStyle = fill; ctx.fill();
  }
  function text(ctx, value, x, y, size, color, max = 940) {
    ctx.font = '800 ' + size + 'px ' + sans;
    ctx.fillStyle = color;
    ctx.textBaseline = 'middle';
    ctx.fillText(value, x, y, max);
  }
  function laneField(ctx, time, accent) {
    const horizon = 470, center = 550;
    ctx.save();
    for (let row = 0; row < 15; row++) {
      const depth = (row * .073 + (time * .24) % .15) % 1;
      const y = horizon + 1420 * depth * depth;
      const w = 26 + 149 * depth;
      for (let lane = -6; lane <= 6; lane++) {
        const x = center + lane * (17 + 140 * depth) + 34 * Math.sin(time * .8) * depth;
        ctx.globalAlpha = .18 + .36 * depth;
        rectangle(ctx, x - w / 2, y, w, 14 + 59 * depth, (row + lane) % 5 === 0 ? accent : '#57686e', 3);
        ctx.globalAlpha *= .75;
        rectangle(ctx, x - .39 * w, y + 5 + 6 * depth, .62 * w, 4 + 4 * depth, '#fef5cf', 1);
      }
    }
    ctx.restore();
  }
  function render(s, id, t, H) {
    const accent = s.palette?.[2] || '#ffd164';
    const bg = {base:['#102526','#0e1c22','#0c1319'],seed:12,grid:true,dust:22};
    K.frame(id,t,H,bg,{push:.009,beats:[.35,1.2,2.53],beat:.028});
    const ctx = H.$(id + 'hook_board').getContext('2d');
    ctx.clearRect(0,0,1080,1920);
    laneField(ctx,t,accent);
    rectangle(ctx,48,105,984,460,'#102024e8',22);
    text(ctx,'规模场景示意',82,152,34,accent);
    text(ctx,'10,000',79,287,176,'#fbf8e6');
    text(ctx,s.scale_example,87,425,66,accent);
    text(ctx,'下方为本机实际运行',89,510,35,'#d5e2cf');
    for (let i = 0; i < 7; i++) {
      ctx.save();
      const offset = (t * 88 + i * 34) % 238;
      ctx.translate(799 + (i % 3) * 58, 104 + offset);
      ctx.rotate(-.26 + .35 * Math.sin(i + t));
      ctx.globalAlpha = .28 + .34 * (i % 3) / 2;
      rectangle(ctx,0,0,93,57,i % 3 === 0 ? accent : '#7b9995',5);
      rectangle(ctx,12,16,66,4,'#fff4cd',2);
      rectangle(ctx,12,29,40,4,'#fff4cd',2);
      ctx.restore();
    }

    const frame = H.frame(s, t);
    if (!frame) throw Error('缺少开头真实操作画面');
    const x = 47, y = 626, width = 986, screenHeight = 552;
    ctx.save();
    ctx.shadowColor='#070b14'; ctx.shadowBlur=35; ctx.shadowOffsetY=17;
    rectangle(ctx,x,y,width,screenHeight + 78,'#fbf4dc',20);
    ctx.restore();
    rectangle(ctx,x,y,width,71,accent,14);
    text(ctx,'本机实录  /  虚构数据',x+26,y+36,35,'#172b30');
    ctx.save();
    ctx.beginPath(); ctx.rect(x+10,y+76,width-20,screenHeight-6); ctx.clip();
    ctx.drawImage(frame,x+10,y+76,width-20,screenHeight-6);
    ctx.restore();
    if (t >= (s.hook_result_at || 1.68)) {
      const reveal = Math.min(1,(t-(s.hook_result_at || 1.68))/.38);
      ctx.save();
      ctx.globalAlpha=.3+.7*reveal;
      const cardY=1314+37*(1-reveal);
      rectangle(ctx,55,cardY,970,117,'#132a27',13);
      rectangle(ctx,55,cardY,10,117,accent,4);
      text(ctx,s.hook_status,88,cardY+59,47,'#fff4cd');
      ctx.restore();
    }
  }
  window.VISUALS['listing-queue_hook'] = {
    bg:'#111e22',
    build(s,id) { return K.layers(id,'<canvas width="1080" height="1920" id="'+id+'hook_board"></canvas>'); },
    anim:render,
    sfx(s) { return [[.36,'tick'],[s.hook_result_at || 1.68,'ding']]; }
  };
})();
