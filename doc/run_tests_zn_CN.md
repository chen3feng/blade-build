测试支持
-------------
Blade对测试驱动开发提供了完善的支持 ，可以通过命令自动运行测试程序。

Blade test支持增量测试 ，可以加快tests的执行。

已经Pass 的tests 在下一次构建和测试时不需要再跑，除非：

* tests 的任何依赖变化导致其重新生成。
* tests 依赖的测试数据改变，这种依赖为显式依赖，用户需要使用BUILD文件指定，如testdata。
* tests 所在环境变量发生改变。
* test arguments 改变。
* Fail 的test cases ，每次都重跑。

如果需要使用全量测试，使用--full-test option, 如 blade test common/... --full-test ， 全部测试都需要跑。
另外，cc_test 支持了 always_run 属性，用于在增量测试时，不管上次的执行结果，每次总是要跑。
```python
cc_test(
    name = 'zookeeper_test',
    srcs = 'zookeeper_test.cc',
    always_run = True
)
```

Blade test支持并行测试，并行测试把这一次构建后需要跑的test cases并发地run。
blade test [targets] --test-jobs N
-t, --test-jobs N 设置并发测试的并发数，Blade会让N个测试进程并行执行

对于某些因为可能相互干扰而不能并行跑的测试，可以加上 exclusive 属性
```python
cc_test(
    name = 'zookeeper_test',
    srcs = 'zookeeper_test.cc',
    exclusive = True
)
```
