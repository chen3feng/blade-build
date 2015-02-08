mkdir -p foo.classes bar.classes
javac -d foo.classes foo/src/main/java/org/blade/foo/Foo.java
javac -cp foo.classes -d bar.classes bar/src/main/java/org/blade/bar/Bar.java
jar cvfe bar.jar org.blade.bar.Bar -C foo.classes . -C bar.classes org/blade/bar/Bar.class
java -jar bar.jar
