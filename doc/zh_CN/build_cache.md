增量构建
-------
Blade构建是增量，只有需要更新时才会去构建相应的目标及其依赖。

构建缓存
-----------
blade 支持 cache 机制，可以大幅度加快重新构建速度。cache配置使用ccache的配置,
如通过配置 CCACHE_DIR 环境变量指定ccache目录，同一个用户的相同代码库的多个workspace或者多个用户之间就可以共享构建cache。
