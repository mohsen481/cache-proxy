import typer
import uvicorn
from typing import Annotated
from .main import app
cli_app = typer.Typer()

origin_option = Annotated[str, typer.Option(help="target server for forwarding requests")]
port_option = Annotated[int, typer.Option()]


@cli_app.command()
def run_proxy_server(origin: origin_option, port: port_option = 2000):
    app.state.origin = origin #set origin in app state so fastapi functions can use it
    uvicorn.run("cache_proxy.main:app", port=port, reload=False)

