# SWiFT-IR Commands

## swim


```
Usage:

  swim WindowSize [Options] ImageName1 ImageName2
  swim WindowSize [Options] ImageName1 tarx tary ImageName2
  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx
  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty
  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty rota
  swim WindowSize [Options] ImageName1 tarx tary ImageName2 patx paty afm0 afm1 afm2 afm3
  swim WindowSize [Options] ImageName1 tarx tary ImageName2 mf00 mf01 mf02 mf10 mf11 mf12 -
  swim WindowSize [Options] ImageName1 tarx tary ImageName2 mf00 mf01 mf02 mf10 mf11 mf12 ??

 Where:

  WindowSize: either # (x and y) or #x# (x by y, such as "2048x1024")
  Options:
    -x expr: addx = MUL*eval_expr(expr)
    -y expr: addy = MUL*eval_expr(expr)
    -m expr: MUL = eval_expr(expr)
    -i expr: niter = atoi(expr)
    -w expr: wht_expon = eval_expr(expr);  whiten = 1;  if(wht_expon == 0.0) whiten = 0;
    -A apodize = 0
    -V no_vert = 1
    -H no_hor = 1
    -r reverse = 1
    -k str: keepimg = str
    -t snrthr,xthr,ythr: set thresholds
```

## iavg


```
Usage:

  iavg [Options] ImageName

 Where:

  Options:
    -r: reverse video
    -e: fill black top edge for newjosh WRE's
    -h: hv_hists
    -q: more quiet
    -a: mode = 0
    -s: mode = 5
    -i: mode = 6
    -p: mode = 7
    -p#: mode = 7 pcount = #
    -#: mode = #
    -m: xramph and xrampl
    -+: add = 1
    --: sub = 1
    -b #: black = #+2
    -w #: white = #+2
```

## mir

```
Enter a MIR command (? for help) > ?

MIR is Multiple Image Rendering

Commands:
  X for eXchange
  I for interpolation 0, 1, 2
  a new reverse mapping: mi00 mi01 mi02  mi10 mi11 mi12
  A new forward mapping: mf00 mf01 mf02  mf10 mf11 mf12
  G new global mapping:  mg00 mg01 mg02  mg10 mg11 mg12
  S scale multipliers: oscalex oscaley iscalex iscaley
  O offsets: ooffx ooffy ioffx ioffy
  B bounds of output region: owid oht obpp twid tht trans
  D directory prefix for all input file names
  F read a new file
  R fill bounding box rect from src file & current mf[][]
  Z zero the drawing space
  V reverse video?
  W write a file?
  # for comment to end of line
  E to Exit
```
