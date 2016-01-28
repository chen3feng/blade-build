	.text
	.globl	asm1
	.type	asm1, @function
asm1:
	pushq	%rbp
	movq	%rsp, %rbp
	popq	%rbp
	ret
