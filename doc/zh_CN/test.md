# 测试支持

Blade对测试驱动开发提供了完善的支持 ，可以通过命令自动运行测试程序。

## 增量测试
Blade test支持增量测试 ，可以加快tests的执行。

已经Pass 的tests 在下一次构建和测试时不需要再跑，除非：

* tests 的任何依赖变化导致其重新生成。
* tests 依赖的测试数据改变，这种依赖为显式依赖，用户需要使用BUILD文件指定，如testdata。
* tests 所在环境变量发生改变。
* test arguments 改变。
* Fail 的test cases ，每次都重跑。

## 全量测试

如果需要使用全量测试，使用--full-test option, 如 blade test common/... --full-test ， 全部测试都需要跑。
另外，cc_test 支持了 always_run 属性，用于在增量测试时，不管上次的执行结果，每次总是要跑。
```python
cc_test(
    name = 'zookeeper_test',
    srcs = 'zookeeper_test.cc',
    always_run = True
)
```

## 并行测试

Blade test支持并行测试，并行测试把这一次构建后需要跑的test cases并发地run。
blade test [targets] --test-jobs N
-t, --test-jobs N 设置并发测试的并发数，Blade会让N个测试进程并行执行

## 非并行测试
对于某些因为可能相互干扰而不能并行跑的测试，可以加上 exclusive 属性
```python
cc_test(
    name = 'zookeeper_test',
    srcs = 'zookeeper_test.cc',
    exclusive = True
)
```


## 测试覆盖率
构建和运行测试时，加上--coverage参数，blade就会加入覆盖率相关的编译选项，目前仅支持C++和java。

C/C++测试覆盖率，是通过gcc的[gcov](https://gcc.gnu.org/onlinedocs/gcc/Gcov.html)实现的。测试运行完后，需要自己执行gcov或者lcov之类的第三方工具生成测试覆盖报告。

java测试覆盖率，是通过jacoco库来生成的，具体请阅读[使用说明](../../java/README.md)。


## 跳过指定的测试
Blade支持通过--skip-tests参数显式地跳过指定的测试，当需要批量运行大量的测试，而又期望跳过某些测试时，这个选项就很有用。例如：
```bash
blade test base/... --skip-tests=base/string,base/encoding:hex_test
```
表示运行base目录下所有的测试，但是跳过base/string下所有的测试以及base/encoding:hex_test。
