# 安装

执行install脚本即可安装到~/bin下，目前因还在开发阶段，变化还比较快，以软链方式安装，install后不能删除checkout出来的原始目录。
目前blade生成scons脚本，因此还需要安装scons 2.0以上版本。如果用ninja来做后端，则需要安装ninja。
Blade 支持 Python 2.7.x 和 python3.4+。

install使得可以在任何目录下直接执行

```bash
$ blade
```

命令。
如果不行，确保~/bin在你的PATH环境变量里，否则修改 ~/.profile，加入

```bash
export PATH=~/bin:$PATH
```

然后重新登录即可。
