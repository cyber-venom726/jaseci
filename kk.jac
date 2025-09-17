


 def f12(a:int, *arg:list[int], x:int=1, y:int=2,**kwargs:dict){

    print('a:', a);
    print('arg:', arg);
    print('x:', x);
    print('y:', y);
 }


 with entry{
    # f12(10, 20, 30, x=100, y=200);
    f12(10, 20, 30, 40);
    f12(10);
 }
