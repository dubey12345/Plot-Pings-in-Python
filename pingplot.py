import signal
import sys
import time
import os
import numpy as np
import datetime
import re
import argparse 
from optparse import OptionParser

__version__ = "1.1.0"

ping_flag = 'n'
if sys.platform != 'win32':
    ping_flag = 'c'

def pinger(host, n):
    if sys.platform != 'win32':
        proc = os.popen(f"ping -{ping_flag} {n} {host}")
    else:
        proc = os.popen(f"chcp 437 & ping -{ping_flag} {n} {host}")
    result = ''.join(proc.readlines())
    proc.close()
    return result

def call_pinger(host, n, ping, loss, t):
    out = pinger(host, n)
    try:
        if sys.platform == 'win32':
            loss_idx = float(re.search(r"\d+(?=% loss)", out).group(0))
            ping_idx = float(re.search(r"(?<=Average =) \d+", out).group(0))
           

        else:
            loss_idx = float(re.search(r"\d+\.\d+(?=% packet loss)", out).group(0))
            ping_idx = float(out.split('/')[-3])
    except:
        ping_idx = np.nan
        loss_idx = 100.
    ping = np.append(ping, ping_idx)
    loss = np.append(loss, loss_idx)
    t = np.append(t, time.time())
    return ping, loss, t, out

def write_log(log_file, log_body):
    log_file.write(f"TIME: {datetime.datetime.now().ctime()}\n{log_body}\n\n")

def plot_gen(ping, now, nans, host, interactive=False, size="1280x640"):
    if not interactive:
        import matplotlib
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    size = [int(dim) for dim in size.split('x')]
    datestr = now[0].ctime().split()
    datestr = datestr[0] + " " + datestr[1] + " " + datestr[2] + " " + datestr[-1]
    plt.figure(figsize=(size[0] / 80., size[1] / 80.))
    plt.plot(now[~nans], ping[~nans], drawstyle='steps')
    plt.title(f"Ping Results for {host}")
    plt.ylabel("Latency [ms]")
    plt.xlabel(f"Time, {datestr} [GMT-{time.timezone // 3600}]")
    plt.xticks(size=10)
    plt.yticks(size=10)
    plt.ylim(ping[~nans].min() - 5, ping[~nans].max() + 5)
    start = []
    finish = []
    for i in range(len(nans)):
        if nans[i]:
            if i == 0 or nans[i] != nans[i - 1]:
                start.append(i)
            if i == len(nans) - 1 or nans[i + 1] != nans[i]:
                finish.append(i)
    for i in range(len(start)):
        plt.axvspan(now[start[i]], now[finish[i]], color='red')
    return plt

def signal_handler(signum, frame, log_file=None, ping=None, now=None, nans=None, opts=None):
    print("\nSIGTERM received, generating output files before exiting...")
    if opts.log and log_file is not None:
        log_file.write(f"\nGraceful shutdown at {datetime.datetime.now().ctime()}\n")
        log_file.close()
        print(f"Saved log file {log_file.name}")
    if opts.fsave and ping is not None:
        if len(ping[~nans]) == 0:
            print("Error: cannot generate plot; no data collected.")
        else:
            plt = plot_gen(ping, now, nans, opts.host, opts.plot, opts.size)
            plot_name = f"pingplot_v{__version__}_{opts.host}_{datetime.datetime.now().isoformat()}.png"
            plt.savefig(plot_name)
            print(f"Saved plot {plot_name}")
    sys.exit(0)

def main(argv=None):
    if not argv:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="PingPlot - Ping host and generate ping vs time plot.")
    parser.add_argument("-p", "--plot", action="store_true", help="Generate plot after data collection is finished.")
    parser.add_argument("-f", "--file", dest="fsave", action="store_true", help="Save plot to file in the current directory.")
    parser.add_argument("-H", "--host", default="google.com", help="Hostname to ping.")
    parser.add_argument("-n", "--num", default=1, type=int, help="Number of packets to send.")
    parser.add_argument("-t", "--dt", default=0.5, type=float, help="Delay between pings in seconds.")
    parser.add_argument("-l", "--log", action="store_true", help="Log the output to a file.")
    parser.add_argument("-s", "--size", default="1280x640", help="Size of the plot.")

    opts = parser.parse_args(argv)
    ping = np.array([])
    loss = np.array([])
    t = np.array([])
    now = np.array([])
    cnt = 0
    if opts.log or opts.fsave:
        now_time = datetime.datetime.now()
        date_str = now_time.isoformat()[:-7][:10]
        time_str = f"{now_time.hour}h{now_time.minute}m{now_time.second}s"
        stamp = date_str + "_" + time_str
        log_name = f"pingplot_v{__version__}_{opts.host}_{stamp}.log"
        plot_name = f"pingplot_v{__version__}_{opts.host}_{stamp}.png"
        if opts.log:
            log_file = open(log_name, 'w')
            log_file.write(f"PingPlot Version {__version__} - Log File\n\n\n")
    signal.signal(signal.SIGTERM, lambda signum, frame: signal_handler(
        signum, frame, log_file=log_file if opts.log else None, ping=ping, now=now, nans=np.isnan(ping), opts=opts))
    print(f"PingPlot Version {__version__} -- by ccampo\n")
    print("{0:^23}\n=======================".format("Run Parameters"))
    print("{0:>17} {1}".format("Hostname:", opts.host))
    print("{0:>17} {1}".format("Ping interval:", str(opts.dt) + " s"))
    print("{0:>17} {1}".format("Packets per ping:", opts.num))
    print("\n\nPress CTRL+C to quit...\n")
    print("{0:^15} {1:^15} {2:^15} {3:^15} {4:^15}\n".format("AVG. PING", "PACKET LOSS", "NUM. PINGS", "NUM. TIMEOUTS",
                                                             "TIME ELAPSED"))
    while True:
        try:
            ping, loss, t, out = call_pinger(opts.host, opts.num, ping, loss, t)
            now = np.append(now, datetime.datetime.now())
            cnt += 1
            mean_loss = loss.mean()
            nans = np.isnan(ping)
            if len(ping[~nans]) > 0:
                mean_ping = ping[~np.isnan(ping)].mean()
            else:
                mean_ping = np.nan
            if opts.log:
                write_log(log_file, out)
            time.sleep(opts.dt)
            delta_t = datetime.timedelta(seconds=(round(time.time() - t[0], 0)))
            sys.stdout.write("\r{0:^15.8} {1:^15.10} {2:^15} {3:^15} {4:^15}".format(str(round(mean_ping, 2)) + " ms",
                                                                                     str(round(mean_loss, 2)) + " %",
                                                                                     cnt * opts.num, len(ping[nans]),
                                                                                     str(delta_t)))
            sys.stdout.flush()
        except KeyboardInterrupt:
            break
    print("\n")
    if opts.log:
        print(f"Saved log file {log_name}")
        log_file.close()
    if opts.fsave or opts.plot:
        if len(ping[~nans]) == 0:
            print("Error: cannot generate plot; no data collected. Please check your connection.")
            return 2
        plt = plot_gen(ping, now, nans, opts.host, opts.plot, opts.size)
        if opts.fsave:
            print(f"Saved plot {plot_name}")
            plt.savefig(plot_name)
        if opts.plot:
            plt.show()
    return 2

if __name__ == "__main__":
    main()
