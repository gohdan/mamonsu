# -*- coding: utf-8 -*-

import logging
import signal
import sys
import codecs
import os
import string

import mamonsu.lib.platform as platform
from mamonsu.lib.parser import parse_args, print_total_help
from mamonsu.lib.config import Config
from mamonsu.lib.supervisor import Supervisor
from mamonsu.lib.plugin import Plugin
from mamonsu.lib.zbx_template import ZbxTemplate
from mamonsu.lib.get_keys import GetKeys

def is_any_equal(iterator):
   length = len(iterator)
   return len(set(iterator)) < length

def start():
    default_name = "default_template_name"

    def quit_handler(_signo=None, _stack_frame=None):
        logging.info("Bye bye!")
        sys.exit(0)

    signal.signal(signal.SIGTERM, quit_handler)
    if platform.LINUX:
        signal.signal(signal.SIGQUIT, quit_handler)

    commands = sys.argv[1:]
    if len(commands) > 0:
        tool = commands[0]
        if tool == '-h' or tool == '--help':
            print_total_help()
        elif tool == 'bootstrap':
            from mamonsu.tools.bootstrap.start import run_deploy
            sys.argv.remove('bootstrap')
            return run_deploy()
        elif tool == 'report':
            from mamonsu.tools.report.start import run_report
            sys.argv.remove('report')
            return run_report()
        elif tool == 'tune':
            from mamonsu.tools.tune.start import run_tune
            sys.argv.remove('tune')
            return run_tune()
        elif tool == 'zabbix':
            from mamonsu.tools.zabbix_cli.start import run_zabbix
            sys.argv.remove('zabbix')
            return run_zabbix()
        elif tool == 'agent':
            from mamonsu.tools.agent.start import run_agent
            sys.argv.remove('agent')
            return run_agent()
        elif tool == 'export' and len(commands) > 2:
            name = string.strip(commands[2], '.xml')
            args, commands = parse_args(name)
            print("this is args", args)
            print("this is commands", commands)
            cfg = Config(args.config_file, args.plugins_dirs)

            if commands[1] == 'zabbix-parameters':
                # zabbix agent keys generation
                plugins = []
                for klass in Plugin.only_child_subclasses():
                    plugins.append(klass(cfg))
                types = args.plugin_type.split(',')

                if len(types) > 1:
                    if is_any_equal(types):
                        print_total_help()
                if len(types) > 1:
                    args.plugin_type = 'all'
                if args.plugin_type == 'pg' or args.plugin_type == 'sys' or args.plugin_type == 'all':
                    template = GetKeys()
                    with codecs.open(args.filename, 'w', 'utf-8') as f:
                        f.write(template.txt(args.plugin_type, plugins))  # pass command type
                        sys.exit(0)

            elif commands[1] == 'config':
                with open(commands[2], 'w') as fd:
                    cfg.config.write(fd)
                    sys.exit(0)
            elif commands[1] == 'template':
                plugins = []
                for klass in Plugin.only_child_subclasses():
                    plugins.append(klass(cfg))
                template = ZbxTemplate(args.template, args.application)
                with codecs.open(args.template, 'w', 'utf-8') as f:
                    f.write(template.xml(plugins))
                    sys.exit(0)
            elif commands[1] == 'zabbix_template':
                Plugin.Type = 'agent'  # change plugin type for template generator
                plugins = []
                for klass in Plugin.only_child_subclasses():
                    # print(klass.__name__)
                    if klass.__name__ == 'PgLocks' or klass.__name__ == 'PgStatProgressVacuum' or  \
                            klass.__name__ == 'Connections' or klass.__name__ == 'Memory' \
                            or klass.__name__ == 'OpenFiles':
                        # generate template for
                        # agent only for two plugins for now
                        plugins.append(klass(cfg))
                template = ZbxTemplate(args.zabbix_template, args.application)
                with codecs.open(args.zabbix_template, 'w', 'utf-8') as f:
                    f.write(template.xml(plugins))
                    sys.exit(0)
            else:
                print_total_help()

    args, commands = parse_args(default_name)
    if len(commands) > 0:
        print_total_help()
    cfg = Config(args.config_file, args.plugins_dirs)

    # simple daemon
    if args.daemon:
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except Exception as e:
            sys.stderr.write('Can\'t fork: {0}\n'.format(e))
            sys.exit(2)

    # write pid-file
    if args.pid is not None:
        try:
            with open(args.pid, 'w') as pidfile:
                pidfile.write(str(os.getpid()))
        except Exception as e:
            sys.stderr.write('Can\'t write pid file, error: %s\n'.format(e))
            sys.exit(2)

    supervisor = Supervisor(cfg)

    try:
        logging.info("Start mamonsu")
        supervisor.start()
    except KeyboardInterrupt:
        quit_handler()