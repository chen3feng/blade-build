增量构建
-------
Blade构建是增量，只有需要更新时才会去构建相应的目标及其依赖。

构建缓存
-----------
blade 还支持 cache 机制，可以大幅度加快构建速度。
blade 支持两种cache
* ccache , cache配置使用ccache的配置, 如通过配置 CCACHE_DIR 环境变量指定ccache目录。
* ccache 没有安装，则使用scons cache, 配置细节如下

scons cache需要一个目录，依次按以下顺序检测：
* 命令行参数--cache-dir
* 环境变量BLADE_CACHE_DIR
* 如果均未配置，则不启用cache。
* 空的BLADE_CACHE_DIR变量或者不带参数值的--cache-dir=, 则会禁止cache。

--cache-size 如不指定，则默认为2G，如指定，则使用用户指定的以Gigabyte为单位的大小的cache。
如 --cache-dir='~/user_cache' --cache-size=16 (16 G)大小cache。
用户可以根据需要配置大小，超出大小blade会执行清理工作，限制cache大小在用户指定的cache大小，
请谨慎设置这个大小，因为涉及到构建速度和机器磁盘空间的占用。
