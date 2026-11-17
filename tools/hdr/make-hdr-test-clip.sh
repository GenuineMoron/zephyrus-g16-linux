#!/bin/sh
# Make a 20 s HDR10 (BT.2020 + PQ) test clip: five patches at 100, 203 (SDR white),
# 400, 616 (this panel's peak) and 1000 nits on top, a 0-1000 nit ramp below.
# In SDR every patch from 203 up looks the same; in HDR they get brighter step by step.
# Play: mpv --fs --vo=gpu-next --target-colorspace-hint=yes "$out"
set -eu
out=${1:-${XDG_CACHE_HOME:-$HOME/.cache}/zephyrus/hdr-test-pq1000.mkv}
mkdir -p "$(dirname "$out")"
# 10-bit limited-range luma for each level (PQ, SMPTE ST 2084): 509 573 636 676 723
lum='if(lt(Y,H/2), if(lt(X,W/5),509, if(lt(X,2*W/5),573, if(lt(X,3*W/5),636, if(lt(X,4*W/5),676,723)))), 64+659*X/W)'
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "color=black:s=2560x1600:r=30:d=20,format=yuv420p10le" \
  -vf "geq=lum='$lum':cb=512:cr=512,drawtext=text='100   203 (SDR white)   400   616 (panel peak)   1000 nits':fontcolor=0x808080:fontsize=40:x=40:y=40,setparams=range=tv:color_primaries=bt2020:color_trc=smpte2084:colorspace=bt2020nc" \
  -c:v libx265 -preset ultrafast -pix_fmt yuv420p10le \
  -color_primaries bt2020 -color_trc smpte2084 -colorspace bt2020nc -color_range tv \
  -x265-params "log-level=error:hdr10=1:repeat-headers=1:colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:range=limited:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400" \
  "$out"
echo "$out"
