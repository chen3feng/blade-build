# 安装 #

执行install脚本即可安装到~/bin下，目前因还在开发阶段，变化还比较快，以软链方式安装，install后不能删除checkout出来的原始目录。
Blade 用 ninja 做后端，还需要安装ninja。
Blade 支持 Python 2.7.x，对 python 3.x 的支持还在准备中。

install使得可以在任何目录下直接执行

```bash
$ blade
usage: blade [-h] [--version] {build,run,test,clean,query,dump} ...
blade: error: too few arguments
Blade(error): Failure
```

命令。
如果不行，确保~/bin在你的PATH环境变量里，否则修改 ~/.profile，加入

```bash
export PATH=~/bin:$PATH
```

然后重新登录即可。
