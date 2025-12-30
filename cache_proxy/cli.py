import typer
import uvicorn
from typing import Annotated
from .main import app


cli_app = typer.Typer()

origin_option = Annotated[str, typer.Option(help="target server for forwarding requests")]
port_option = Annotated[int, typer.Option()]


@cli_app.command()
def run_proxy_server(origin: origin_option, port: port_option = 2000):
    #store "origin" and "port" in app state so that fastapi functions can use.
    app.state.origin=origin 
    app.state.port=port
    uvicorn.run(app,host='0.0.0.0',port=port, reload=False)

