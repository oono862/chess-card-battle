# BBC (B.B.C) モジュール
# リファクタリングされたモジュール群をまとめるパッケージ
import logging

# Set a conservative default log level for the package so that
# debug messages are suppressed during normal runs. Individual
# modules can raise the level when needed.
logging.basicConfig(level=logging.WARNING)
