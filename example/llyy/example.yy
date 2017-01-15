%{
    #include <stdio.h>
    int yylex(void);
    void yyerror(const char *);
%}

%token INTEGER

%%

program:
        program expr '\n'         { printf("%d\n", $2); }
        |
        ;

expr:
        INTEGER
        | expr '+' expr           { $$ = $1 + $3; }
        | expr '-' expr           { $$ = $1 - $3; }
        ;

%%

void yyerror(const char *s) {
    fprintf(stderr, "%s\n", s);
}

