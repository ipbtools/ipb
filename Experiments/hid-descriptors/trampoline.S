.text
.globl _call_indirect_getter
.p2align 2
// x0 = getter, x1 = 32-byte result buffer. Static getter takes no arguments; result via x8.
_call_indirect_getter:
    mov x8, x1
    mov x16, x0
    br  x16
