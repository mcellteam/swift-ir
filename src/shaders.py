#!/usr/bin/env python3

ann_shader = '''void main() { setPointMarkerBorderColor(prop_ptColor()); 
setPointMarkerBorderWidth(prop_ptWidth()); 
setPointMarkerSize(prop_size());}
'''

shader_default = '''#uicontrol invlerp normalized
void main() {
  emitGrayscale(normalized());
}
'''

shader_default_ = '''#uicontrol vec3 color color(default="white")
#uicontrol float brightness slider(min=-1, max=1, step=0.01)
#uicontrol float contrast slider(min=-1, max=1, step=0.01)
void main() {
  emitRGB(color *
          (toNormalized(getDataValue()) + brightness) *
          exp(contrast));
}
'''

shader_test1 = '''#uicontrol vec3 color color(default="red")
#uicontrol float brightness slider(min=-1, max=1)
#uicontrol float contrast slider(min=-3, max=3, step=0.01)
void main() {
  emitRGB(color *
          (toNormalized(getDataValue()) + brightness) *
          exp(contrast));
}
'''

shader_test2 = '''#uicontrol vec3 color color(default="white")
#uicontrol float min slider(default=0, min=0, max=1, step=0.01)
#uicontrol float max slider(default=1, min=0, max=1, step=0.01)
#uicontrol float brightness slider(default=0, min=-1, max=1, step=0.1)
#uicontrol float contrast slider(default=0, min=-3, max=3, step=0.1)

float s(float x, float min, float max) {
  return (x - min) / (max - min);
}

void main() {
  emitRGB(
    color * vec3(
      s(toNormalized(getDataValue()), min, max) + brightness,
      s(toNormalized(getDataValue()), min, max) + brightness,
      s(toNormalized(getDataValue()), min, max) + brightness
    ) * exp(contrast)
  );
  
}
'''


colormapJet = '''void main() {
  float v = toNormalized(getDataValue(0));
  vec4 rgba = vec4(0,0,0,0);
  if (v != 0.0) {
    rgba = vec4(colormapJet(v), 1.0);
  }
  emitRGBA(rgba);
}
'''