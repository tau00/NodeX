#version 440
// Faint dot grid (Board.qml `grid`): a round ~1.15 px dot at the centre of every `cell`-sized
// cell, premultiplied. Uniform names match the ShaderEffect's QML properties.
// Rebuild grid.frag.qsb with: python tools/build_shaders.py
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float cell;
    vec2 origin;
    vec2 res;
    float alpha;
};

void main() {
    vec2 c = mod(qt_TexCoord0 * res - origin, cell) - 0.5 * cell;
    float a = alpha * qt_Opacity * (1.0 - smoothstep(0.9, 1.45, length(c)));
    fragColor = vec4(a, a, a, a);
}
