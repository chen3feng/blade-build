# 命令行参考

## 基本命令行语法

```bash
blade <子命令> [选项]... [目标模式]...
```

## 子命令

subcommand是一个子命令，目前有：

* `build` 构建指定的目标
* `test`  构建并且运行指定的测试
* `clean` 清除指定目标的构建结果
* `dump`  输出一些内部信息
* `query` 查询目标的依赖项与被依赖项
* `run`   构建并运行单个可执行的目标

## 目标模式

每个 `BUILD` 文件中的 `name` 属性描述了一个构建目标，在命令行，一些配置项和 BUILD 的某些属性都支持目标模式。

目标模式是一个空格分开的列表，支持的格式：

* `path:name` 表示 path 中的某个 target
* `path:*` 表示 path 中所有目标，但不包含其子目录
* `path` 是 `path:*` 的简写形式
* `path/...` 表示path中所有目标，并递归包括所有子目录
* `:name` 表示当前目录下的某个目标

如果 `path` 以 `//` 开始，则表示从[工作空间](workspace.md)的根目录开始。

如果没有指定目标模式，则默认为当前目录下的所有目标（不包含子目录），如果当前目录下没有 BUILD 文件，就会失败。
当指定 `...` 作为结尾目标时，如果其路径存在，即使展开为空，也总不会失败。

对于 `...` 目标模式，Blade 会递归搜索 `BUILD` 文件，如果需要排除某些目录，在其中放一个空的 `.bladeskip` 文件即可。

## 子命令选项

不同子命令支持的选项不一样，具体请执行 `blade <subcommand> --help` 查看

下面是一些常用的命令行选项：

* -m32,-m64            指定构建目标位数，默认为自动检测
* -p PROFILE           指定debug/release，默认release
* -k, --keep-going     构建过程中遇到错误继续执行（如果是致命错误不能继续）
* -j N,--jobs=N        N路并行构建（Blade默认开启并行构建，自己计算合适的值）
* -t N,--test-jobs=N   N路并行测试，多CPU机器上适用
* --verbose            完整输出所运行的每条命令行
* –h, --help           显示帮助
* --color=yes/no/auto  是否开启彩色
* --exclude-targets    以逗号分割的加载时要排除的目标模式
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

# 构建 app 目录下所有目标，但排除其 sub 子目录
blade build app... --exclude-targets=app/sub...

# 构建和测试从WORKPACE根出发，common及其所有子目录下的所有目标
blade test //common/...

blade test base/...

# 构建和测试base子目录下名为`string_test`的目标
blade test base:string_test
```

## 命令行补全

执行[安装](misc.md)命令后有简单的命令行补全。
安装 [autocomplete](https://pypi.org/project/argcomplete/) 后会得到完整的命令行补全。

### 安装 argcomplete

```console
pip install argcomplete
```

非 root 安装用加上 `--user` 参数

### 启用

修改 `~/.bashrc`:

```bash
eval "$(register-python-argcomplete blade)"
```
