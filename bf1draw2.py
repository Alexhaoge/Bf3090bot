from io import BytesIO
from base64 import b64encode
from matplotlib import pyplot as plt
from matplotlib.dates import DateFormatter
from datetime import datetime, timezone

def draw_server_array_matplotlib(res: dict) -> str:
    local_tz = datetime.now(timezone.utc).astimezone().tzinfo
    times = [datetime.fromisoformat(t) for t in res['timeStamps']]
    fig, ax = plt.subplots(1)
    fig.autofmt_xdate()
    plt.plot(times, res['soldierAmount'])
    xfmt = DateFormatter('%m-%d %H:%M', tz=local_tz)
    ax.xaxis.set_major_formatter(xfmt)
    img = BytesIO()
    plt.savefig(img, format='png')
    return 'base64://' + b64encode(img.getvalue()).decode('ascii')