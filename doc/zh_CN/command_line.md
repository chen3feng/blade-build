# 命令行参考

## 基本命令行语法

```bash
blade <subcommand> [options]... [targets]...
```

## 子命令

subcommand是一个子命令，目前有：

* build 表示构建项目
* test  表示构建并且跑单元测试
* clean 表示清除目标的构建结果
* query 查询目标的依赖项与被依赖项
* run   构建并run一个单一目标

## Target语法

targets是一个空格分开的列表，支持的格式：

* path:name 表示path中的某个target
* path表示path中所有targets
* path/... 表示path中所有targets，并递归包括所有子目录
* :name表示当前目录下的某个target

如果没有指定target，则默认为当前目录下的所有目标（不包含子目录），如果当前目录下没有BUILD文件，就会失败。
当指定...作为结尾目标时，如果其路径存在，即使展开为空，也总不会失败。

## 子命令选项

不同子命令支持的选项不一样，具体请执行blade \<subcommand\> --help查看

下面是一些常用的命令行选项

* -m32,-m64            指定构建目标位数，默认为自动检测
* -p PROFILE           指定debug/release，默认release
* -k, --keep-going     构建过程中遇到错误继续执行（如果是致命错误不能继续）
* -j N,--jobs=N        N路并行构建（Blade默认开启并行构建，自己计算合适的值）
* -t N,--test-jobs=N   N路并行测试，多CPU机器上适用
* --verbose            完整输出所运行的每条命令行
* –h, --help           显示帮助
* --color=yes/no/auto  是否开启彩色
* --generate-dynamic   强制生成动态库
* --generate-java      为proto_library 和 swig_library 生成java文件
* --generate-php       为proto_library 和 swig_library 生成php文件
* --gprof              支持 GNU gprof
* --coverage           支持生成覆盖率，目前支持 GNU gcov 和Java jacoco

## 示例

```bash

# 构建当前目录下的所有目标，不包含子目录
blade build

# 构建当前目录以及子目录下所有的目标
blade build ...

# 构建当前目录下名为`urllib`的目标
blade build :urllib

# 构建和测试从WORKPACE根出发，common及其所有子目录下的所有目标
blade test //common/...

blade test base/...

# 构建和测试base子目录下名为`string_test`的目标
blade test base:string_test
```

对于 `...` 目标模式，Blade 会递归搜索 `BUILD` 文件，如果需要排除某些目录，在其中放一个空的 `.bladeskip` 文件即可。
