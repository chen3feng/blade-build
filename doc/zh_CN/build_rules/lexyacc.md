# 构建lex和yacc #

## lex_yacc_library ##

用于定义了lex yacc目标，生成编译器需要的词法分析器与语法分析器。
由于二者通常都是搭配使用，并且编译lex时，通常采用yacc生成的yy.tab.h来定义，而编译yacc生成的yy.tab.cc时，又会调用lex生成的parse函数，整体上形成相互依赖。
因此我们把做成一条规则。srcs 必须为二元列表，后缀分别为ll和yy。

本规则构建时按依赖关系自动调用flex和bison, 并且编译成对应的cc_library，生成正确的头文件

属性：

- recursive=True 生成可重入的C scanner。

也支持大部分 [cc_library 的属性](cc.md#cc_library)。

示例：

```python
lex_yacc_library(
     name = 'parser',
     srcs = [
         'line_parser.ll',
         'line_parser.yy'
     ],
     deps = [
         ":xcubetools",
     ],
     recursive = True
)
```
