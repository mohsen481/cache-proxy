import typer
import uvicorn
from typing import Annotated
from .main import app
import redis


cli_app = typer.Typer()

origin_option = Annotated[str, typer.Option(help="target server for forwarding requests")]
port_option = Annotated[int, typer.Option()]


@cli_app.command()
def start(origin: origin_option, port: port_option = 2000):
    """
    start proxy app
    """
    #store "origin" and "port" in app state so that fastapi functions can use.
    app.state.origin=origin 
    app.state.port=port
    uvicorn.run(app,host='0.0.0.0',port=port, reload=False)

@cli_app.command()
def clear_cache():
    """
    clear all cached data
    """
    try:
        r=redis.Redis()
        keys=r.keys()
        if keys==[]:
            print('nothing to cleare')
        else:
            confirm=typer.confirm("Warning!: this will delete all redis keys on your system.are you sure to cleare?",abort=True)
            r.flushall(asynchronous=False)
            print("CACHE DATA CLEARED SUCCESSFULY")
    except Exception as e:
        print(e)
