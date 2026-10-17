#version 440
// Far-zoom "greek" bars of a node (Node.qml): type, name, one row per port with its stubs and
// value field, antialiased over one screen pixel and accumulated premultiplied. Each rN packs
// two rows (see Node.qml `greek`). Uniform names match the ShaderEffect's QML properties.
// Rebuild greek.frag.qsb with: python tools/build_shaders.py
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 sz;
    float px;
    float nodeW;
    float nameW;
    float typeW;
    vec4 ink;
    vec4 text;
    vec4 faint;
    vec4 field;
    vec4 r0; vec4 r1; vec4 r2; vec4 r3;
    vec4 r4; vec4 r5; vec4 r6; vec4 r7;
    vec4 r8; vec4 r9; vec4 r10; vec4 r11;
    vec4 r12; vec4 r13; vec4 r14; vec4 r15;
};

vec2 p;
vec4 acc;

// coverage of a rounded bar [x0, x1] x [cy - h/2, cy + h/2], antialiased over one pixel
void bar(float x0, float x1, float cy, float h, vec4 c) {
    float r = 0.5 * h;
    vec2 q = vec2(clamp(p.x, x0 + r, max(x0 + r, x1 - r)), cy);
    float d = length(p - q) - r;
    float a = c.a * clamp(0.5 - d / px, 0.0, 1.0);
    acc = mix(acc, vec4(c.rgb, 1.0), a);
}

void row(float f1, float f2) {
    if (f1 < 0.0) return;
    float cy = floor(f1 / 512.0), lx = f1 - cy * 512.0;
    if (abs(p.y - cy) > 9.0) return;
    float lw = floor(f2 / 2048.0), rest = f2 - lw * 2048.0;
    float inp = floor(rest / 1024.0); rest -= inp * 1024.0;
    float outp = floor(rest / 512.0), bw = rest - outp * 512.0;
    if (inp > 0.0) bar(0.0, 0.0, cy, 7.0, vec4(faint.rgb, 0.9));
    if (outp > 0.0) bar(nodeW, nodeW, cy, 7.0, vec4(faint.rgb, 0.9));
    bar(lx, lx + lw, cy, 7.0, vec4(text.rgb, 0.55));
    if (bw > 0.0) {
        float bx1 = nodeW - 12.0 - outp * 4.0;
        bar(bx1 - bw, bx1, cy, 14.0, vec4(field.rgb, 1.0));
    }
}

void main() {
    p = qt_TexCoord0 * sz - vec2(8.0, 18.0);
    acc = vec4(0.0);
    bar(2.0, 2.0 + typeW, -11.0, 7.0, vec4(faint.rgb, 0.8));
    bar(35.0, 35.0 + nameW, 14.0, 9.0, vec4(ink.rgb, 0.7));
    if (p.y > 28.0) {
        row(r0.x, r0.y); row(r0.z, r0.w); row(r1.x, r1.y); row(r1.z, r1.w);
        row(r2.x, r2.y); row(r2.z, r2.w); row(r3.x, r3.y); row(r3.z, r3.w);
        row(r4.x, r4.y); row(r4.z, r4.w); row(r5.x, r5.y); row(r5.z, r5.w);
        row(r6.x, r6.y); row(r6.z, r6.w); row(r7.x, r7.y); row(r7.z, r7.w);
        row(r8.x, r8.y); row(r8.z, r8.w); row(r9.x, r9.y); row(r9.z, r9.w);
        row(r10.x, r10.y); row(r10.z, r10.w); row(r11.x, r11.y); row(r11.z, r11.w);
        row(r12.x, r12.y); row(r12.z, r12.w); row(r13.x, r13.y); row(r13.z, r13.w);
        row(r14.x, r14.y); row(r14.z, r14.w); row(r15.x, r15.y); row(r15.z, r15.w);
    }
    fragColor = acc * qt_Opacity;     // bar() accumulates premultiplied
}
