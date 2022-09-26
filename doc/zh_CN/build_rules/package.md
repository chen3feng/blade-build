# 文件打包 #

用于支持把构建结果和源代码里的一些文件打包

```python
package(
    name = 'server_package',
    type = 'tgz',
    shell = True,
    srcs = [
        # executable
        ('$(location //server:server)', 'bin/server'),
        # conf
        ('//server/conf/server.conf', 'conf/server.conf'),
    ]
)
```

`type`是文件的类型，目前支持的有zip, tar, tar.gz, tgz, tar.bz2, tbz，type会作为输出文件的扩展名。

`shell`是可选项。开启后会在shell中进行打包。pigz作为多核加速打包工具会被默认优先使用打包gzip。

由于打包规则执行比较慢，而且开发阶段一般用不到，因此默认不运行，需要加--generate-package才会运行。
