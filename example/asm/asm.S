	.text
	.globl	asm2
	.type	asm2, @function
asm2:
#ifdef __i386__
	pushl	%ebp
	movl	%esp, %ebp
	popl	%ebp
#endif
#ifdef __x86_64__
	pushq	%rbp
	movq	%rsp, %rbp
	popq	%rbp
#endif
	ret
