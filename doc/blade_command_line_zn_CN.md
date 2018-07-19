命令行参考
---------
```bash
blade `[`action`]` `[`options`]` `[`targets`]`
```

action是一个动作，目前有

* build 表示构建项目
* test  表示构建并且跑单元测试
* clean 表示清除目标的构建结果
* query 查询目标的依赖项与被依赖项
* run   构建并run一个单一目标

targets是一个列表，支持的格式：

* path:name 表示path中的某个target
* path表示path中所有targets
* path/... 表示path中所有targets，并递归包括所有子目录
* :name表示当前目录下的某个target
默认表示当前目录

参数列表：

* -m32,-m64            指定构建目标位数，默认为自动检测
* -p PROFILE           指定debug/release，默认release
* -k, --keep-going     构建过程中遇到错误继续执行（如果是致命错误不能继续）
* -j N,--jobs=N        N路并行编译，多CPU机器上适用
* -t N,--test-jobs=N   N路并行测试，多CPU机器上适用
* --cache-dir=DIR      指定一个cache目录
* --cache-size=SZ      指定cache大小，以G为单位
* --verbose            完整输出所运行的每条命令行
* –h, --help           显示帮助
* --color=yes/no/auto  是否开启彩色
* --generate-dynamic   强制生成动态库
* --generate-java      为proto_library 和 swig_library 生成java文件
* --generate-php       为proto_library 和 swig_library 生成php文件
* --gprof              支持 GNU gprof
* --coverage           支持生成覆盖率，目前支持 GNU gcov 和Java jacoco
