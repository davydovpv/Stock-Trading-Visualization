import random
import json
import gym
from gym import spaces
import pandas as pd
import numpy as np

from render.StockTradingGraph import StockTradingGraph

MAX_ACCOUNT_BALANCE = 2147483647
MAX_NUM_SHARES = 2147483647
MAX_SHARE_PRICE = 5000
MAX_OPEN_POSITIONS = 5
MAX_STEPS = 20000

INITIAL_ACCOUNT_BALANCE = 10000

LOOKBACK_WINDOW_SIZE = 40


# def factor_pairs(val):
#     return [(i, val / i) for i in range(1, int(val**0.5)+1) if val % i == 0]


class StockTradingEnv(gym.Env):
    """A stock trading environment for OpenAI gym"""
    metadata = {'render.modes': ['live', 'file', 'none']}
    visualization = None

    def __init__(self, config):
        # super(StockTradingEnv, self).__init__()

        self.df = config['df']
        self.reward_range = (0, MAX_ACCOUNT_BALANCE)

        # Actions of the format Buy x%, Sell x%, Hold, etc.
        self.action_space = spaces.Box(
            low=np.array([0, 0]), high=np.array([3, 1]), dtype=np.float16)

        # Prices contains the OHCL values for the last five prices
        self.observation_space = spaces.Box(
            low=-np.finfo(np.float32).max, high=np.finfo(np.float32).max, shape=(17, ), dtype=np.float16)

    # def _adjust_prices(self, df):
    #     # adjust_ratio = df['Adjusted_Close'] / df['Close']

    #     df['Open'] = df['Open'] * adjust_ratio
    #     df['High'] = df['High'] * adjust_ratio
    #     df['Low'] = df['Low'] * adjust_ratio
    #     df['Close'] = df['Close'] * adjust_ratio

    #     return df

    def _next_observation(self):
        frame = np.zeros(12)

        # Get the stock data points for the last 5 days and scale to between 0-1
        # CRITICAL POINT HERE
        # =================
        np.put(frame, [0,1,2,3,4,5,6,7,8.9,10,11], [
            self.df.loc[self.current_step: self.current_step + 1, 'open'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'high'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'low'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'close'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'volumefrom'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'MOM'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'RSI'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'HT_DCPERIOD'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'EMA'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'WILLR'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'BBANDS_upper'].values,
            self.df.loc[self.current_step: self.current_step + 1, 'PPO'].values,
        ])

        # Append additional data and scale each value to between 0-1
        obs = np.append(frame, [
            [self.balance],
            [self.max_net_worth],
            [self.shares_held],
            [self.cost_basis],
            [self.total_sales_value],
        ])
        # print(obs)


        return obs

    def _take_action(self, action):
        current_price = random.uniform(
            self.df.loc[self.current_step, "open"], self.df.loc[self.current_step, "close"])

        action_type = action[0]
        amount = action[1]

        if action_type < 1:
            # Buy amount % of balance in shares
            total_possible = int(self.balance / current_price)
            shares_bought = int(total_possible * amount)
            prev_cost = self.cost_basis * self.shares_held
            additional_cost = shares_bought * current_price

            self.balance -= additional_cost
            self.cost_basis = (
                prev_cost + additional_cost) / (self.shares_held + shares_bought)
            self.shares_held += shares_bought

            if shares_bought > 0:
                self.trades.append({'step': self.current_step,
                                    'shares': shares_bought, 'total': additional_cost,
                                    'type': "buy"})

        elif action_type < 2:
            # Sell amount % of shares held
            shares_sold = int(self.shares_held * amount)
            self.balance += shares_sold * current_price
            self.shares_held -= shares_sold
            self.total_shares_sold += shares_sold
            self.total_sales_value += shares_sold * current_price

            if shares_sold > 0:
                self.trades.append({'step': self.current_step,
                                    'shares': shares_sold, 'total': shares_sold * current_price,
                                    'type': "sell"})

        self.net_worth = self.balance + self.shares_held * current_price

        if self.net_worth > self.max_net_worth:
            self.max_net_worth = self.net_worth

        if self.shares_held == 0:
            self.cost_basis = 0

    def step(self, action):
        # Execute one time step within the environment
        self._take_action(action)

        self.current_step += 1

        delay_modifier = (self.current_step / MAX_STEPS)

        reward = self.balance * delay_modifier + self.current_step
        done = self.net_worth <= 0 or self.current_step >= len(
            self.df.loc[:, 'open'].values)

        obs = self._next_observation()

        return obs, reward, done, {}

    def reset(self):
        # Reset the state of the environment to an initial state
        self.balance = INITIAL_ACCOUNT_BALANCE
        self.net_worth = INITIAL_ACCOUNT_BALANCE
        self.max_net_worth = INITIAL_ACCOUNT_BALANCE
        self.shares_held = 0
        self.cost_basis = 0
        self.total_shares_sold = 0
        self.total_sales_value = 0
        self.current_step = 0
        self.trades = []

        return self._next_observation()

    def _render_to_file(self, filename='render.txt'):
        profit = self.net_worth - INITIAL_ACCOUNT_BALANCE

        file = open(filename, 'a+')

        file.write('Step: {}\n'.format(self.current_step))
        file.write('Balance: {}\n'.format(self.balance))
        file.write('Shares held: {} (Total sold: {})\n'.format(self.shares_held, self.total_shares_sold))
        file.write('Avg cost for held shares: {} (Total sales value: {})\n'.format(self.cost_basis, self.total_sales_value))
        file.write('Net worth: {} (Max net worth: {})\n'.format(self.net_worth, self.max_net_worth))
        file.write('Profit: {}\n\n'.format(profit))

        file.close()

    def render(self, mode='live', **kwargs):
        # Render the environment to the screen
        if mode == 'file':
            self._render_to_file(kwargs.get('filename', 'render.txt'))

        elif mode == 'live':
            if self.visualization == None:
                self.visualization = StockTradingGraph(self.df)

            # if self.current_step > LOOKBACK_WINDOW_SIZE:
            self.visualization.render(
                self.current_step, self.net_worth, self.trades, window_size=LOOKBACK_WINDOW_SIZE)

    def close(self):
        if self.visualization != None:
            self.visualization.close()
            self.visualization = None