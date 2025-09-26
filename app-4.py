from collections import OrderedDict
import pandas_market_calendars as mcal
import math
import pandas as pd
from datetime import timedelta 
import time
from datetime import datetime
import plotly.graph_objects as go
import streamlit as st
from tvDatafeed import TvDatafeed, Interval 
import pytz

st.set_page_config( 
    page_title="Demand And Supply zone scanner For Indian Stock Market",  # Meta title
    page_icon="📈",  # Page icon (can be a string, or a path to an image)
    layout="wide",  # Layout configuration
)
# Hide Streamlit style elements
hide_streamlit_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            </style>
            """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# Add a meta description
st.markdown(
    """
    <meta name="description" content="This is a Demand And Supply daily zone scan engine For Indian Stock Market.If you know about drop base rally and rally base rally or rally base drop and drop base drop pattern then this scanner can be useful for you">
    """,
    unsafe_allow_html=True
)

def fetch_stock_data_and_resample(symbol, exchange, n_bars, htf_interval, interval, interval_key):
    try:        
        # Fetch historical data using tvDatafeed
        stock_data = tv.get_hist(symbol=symbol, exchange=exchange, interval=interval, n_bars=n_bars)
        
        # Check if stock_data is None or empty
        if stock_data is not None and not stock_data.empty:  
            stock_data.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'}, inplace=True)
            stock_data.index = stock_data.index.tz_localize('UTC').tz_convert('Asia/Kolkata')

            df = stock_data.round(2)
            
            resample_rules = {
                '10 Minutes': '10min',
                '75 Minutes': '75min',
                '125 Minutes': '125min'
            }

            rule = resample_rules.get(interval_key)
            if rule is None:
                print(f"Warning: No resample rule found for key '{key}'.")
                return None, None  # Exit if no valid rule is found

            df = df.resample(rule=rule, closed='left', label='left', origin=df.index.min()).agg(
                OrderedDict([
                    ('Open', 'first'),
                    ('High', 'max'),
                    ('Low', 'min'),
                    ('Close', 'last'),
                    ('Volume', 'sum')
                ])
            ).dropna()

            stock_data = df.round(2)

        # Fetch historical data for high time frame
        # Check if stock_data_htf is None or empty
        if stock_data is not None and not stock_data.empty:  

            return stock_data
        else:
            print(f"No high time frame data found for {symbol} on {exchange}.")
            return None # Return None if no data is found
            
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None  # Return None in case of an error


def fetch_stock_data(symbol, exchange, n_bars, htf_interval, interval):
    try:
        # print(f"Fetching data for {symbol} on {exchange} with n_bars={n_bars}, htf_interval={htf_interval}, interval={interval}")

        # Fetch historical data using tvDatafeed
        stock_data = tv.get_hist(symbol=symbol, exchange=exchange, interval=interval , n_bars=n_bars)  # Use parameters correctly

        # Check if stock_data is None
        if stock_data is not None and not stock_data.empty:  # Added check for empty DataFrame
            stock_data.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)
            stock_data.index = stock_data.index.tz_localize('UTC').tz_convert('Asia/Kolkata')

            stock_data = stock_data.round(2)
        # Fetch historical data using tvDatafeed

        # Check if stock_data is None
        if stock_data is not None and not stock_data.empty:  # Added check for empty DataFrame

            return stock_data
        else:
            print(f"No data found for {symbol} on {exchange}.")
            return None  # Return None if no data is found
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None  # Return None in case of an error

def calculate_atr(stock_data, length=14):
    stock_data['previous_close'] = stock_data['Close'].shift(1)
    stock_data['tr1'] = abs(stock_data['High'] - stock_data['Low'])
    stock_data['tr2'] = abs(stock_data['High'] - stock_data['previous_close'])
    stock_data['tr3'] = abs(stock_data['Low'] - stock_data['previous_close'])
    stock_data['TR'] = stock_data[['tr1', 'tr2', 'tr3']].max(axis=1)

    def rma(series, length):
        alpha = 1 / length
        return series.ewm(alpha=alpha, adjust=False).mean()

    stock_data['ATR'] = rma(stock_data['TR'], length)
    stock_data['Candle_Range'] = stock_data['High'] - stock_data['Low']
    stock_data['Candle_Body'] = abs(stock_data['Close'] - stock_data['Open'])
    return stock_data

def capture_ohlc_data(stock_data, exit_index, i):
    start_index = max(0, i - 12)
    end_index = min(len(stock_data), exit_index+12 if exit_index is not None else (i + 12))
    ohlc_data = stock_data.iloc[start_index:end_index]
    return ohlc_data
    
def check_golden_crossover(stock_data_htf, pulse_check_start_date):
    result = ""  # Initialize an empty string to store the result
    trend_label = ""  # Initialize trend_label
    try:
        # Calculate EMA20 and EMA50
        stock_data_htf['EMA20'] = stock_data_htf['Close'].ewm(span=20, adjust=False).mean().round(2)
        stock_data_htf['EMA50'] = stock_data_htf['Close'].ewm(span=50, adjust=False).mean().round(2)

        # Drop rows with NaN values in EMA columns
        stock_data_htf.dropna(subset=['EMA20', 'EMA50'], inplace=True)

        # Identify crossover points
        crossover_up = stock_data_htf['EMA20'] > stock_data_htf['EMA50']
        crossover_down = stock_data_htf['EMA20'] < stock_data_htf['EMA50']

        # Localize pulse_check_start_date to 'Asia/Kolkata'
        pulse_check_start_date = pulse_check_start_date.tz_localize('Asia/Kolkata')

        # Find the last index before the target date
        last_index_before_staring_check = stock_data_htf.index[stock_data_htf.index < pulse_check_start_date]

        if not last_index_before_staring_check.empty:
            last_index_before_staring_check = last_index_before_staring_check[-1]

            # Check crossover conditions just before the target date
            if crossover_up.loc[last_index_before_staring_check]:
                # Check if the crossover candle is bullish or bearish
                if stock_data_htf['Close'].loc[last_index_before_staring_check] > stock_data_htf['Open'].loc[last_index_before_staring_check]:
                    result = "Pulse✅ Candle✅"
                else:
                    result = "Pulse✅ Candle❌"
            elif crossover_down.loc[last_index_before_staring_check]:
                # Check if the crossover candle is bullish or bearish
                if stock_data_htf['Close'].loc[last_index_before_staring_check] > stock_data_htf['Open'].loc[last_index_before_staring_check]:
                    result = "Pulse❌ Candle✅"
                else:
                    result = "Pulse❌ Candle❌ "
            else:
                result = "invalid pulse"

            # New logic for trend label
            latest_candle_close = stock_data_htf['Close'].iloc[-1]
            latest_candle_low = stock_data_htf['Low'].iloc[-1]
            latest_candle_high = stock_data_htf['High'].iloc[-1]
            latest_closing_price = round(stock_data_htf['Close'].iloc[-1], 2)
            ema20 = stock_data_htf['EMA20']

            if (latest_candle_close == ema20.iloc[-1] or 
                (latest_candle_low <= ema20.iloc[-1] and latest_candle_high >= ema20.iloc[-1])):
                trend_label = "➡️ sideways"
            elif (latest_candle_close > ema20.iloc[-8] and latest_candle_close > ema20.iloc[-1]):
                trend_label = "✅ Up"
            elif (latest_candle_close < ema20.iloc[-8] and latest_candle_close < ema20.iloc[-1]):
                trend_label = "❌ Down"

        else:
            result = "No data"

    except Exception as e:
        result = f"NA"

    return result, trend_label  # Return the result string and trend label

def is_overlap_less_than_50(stock_data, legin_candle_index):
    # Extract OHLC values for the previous and leg-in candles
    previous_open = stock_data['Open'].iloc[legin_candle_index - 1]
    previous_close = stock_data['Close'].iloc[legin_candle_index - 1]
    legin_open = stock_data['Open'].iloc[legin_candle_index]
    legin_close = stock_data['Close'].iloc[legin_candle_index]

    # Define the bounds for the previous and leg-in candles
    previous_lower_bound = min(previous_open, previous_close)
    previous_upper_bound = max(previous_open, previous_close)

    legin_lower_bound = min(legin_open, legin_close)
    legin_upper_bound = max(legin_open, legin_close)

    # Calculate the overlap
    overlap = max(0, min(previous_upper_bound, legin_upper_bound) - max(previous_lower_bound, legin_lower_bound))

    # Calculate the body lengths
    previous_candle_body = abs(previous_close - previous_open)
    legin_candle_body = abs(legin_close - legin_open)

    # Check if the overlap is less than or equal to 50% of the previous candle's body
    return overlap <= 0.5 * previous_candle_body and overlap < legin_candle_body

from datetime import datetime, timedelta
import pytz

def validate_time_condition(legout_date, entry_date, interval_key):
    time_delay = {
        '1 Minute': timedelta(minutes=15),
        '3 Minutes': timedelta(minutes=75),
        '5 Minutes': timedelta(minutes=75),
        '10 Minutes': timedelta(days=1),
        '15 Minutes': timedelta(days=1)
    }
    
    # Get the required time delay for the given interval key
    require_time_delay = time_delay.get(interval_key, timedelta(days=7))  # Default to 7 days if not found

    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)

    # Convert legout_date to datetime if it's a string
    if isinstance(legout_date, str):
        legout_date = datetime.fromisoformat(legout_date)  # Adjust format as necessary
    legout_date_formatting = legout_date.tz_localize(ist) if legout_date.tzinfo is None else legout_date.astimezone(ist)

    if entry_date is not None:
        # Convert entry_date to datetime if it's a string
        if isinstance(entry_date, str):
            entry_date = datetime.fromisoformat(entry_date)  # Adjust format as necessary
        entry_date_formatting = entry_date.tz_localize(ist) if entry_date.tzinfo is None else entry_date.astimezone(ist)
        return entry_date_formatting > legout_date_formatting + require_time_delay
    else:
        return current_time > legout_date_formatting + require_time_delay
        
def check_legout_covered(it_is_demand_zone, stock_data, i, entry_index, total_risk, reward_value, first_legout_candle_range, entry_price):
    first_legout_half = first_legout_candle_range * 0.50
    legout_covered_limit = (total_risk * reward_value if reward_value == 3 else 5) + entry_price if it_is_demand_zone else (total_risk * reward_value if reward_value == 3 else 5) - entry_price
    
    if entry_index is not None:
        if it_is_demand_zone:
            highest_high = stock_data['High'].iloc[i:entry_index + 1].max()
            return highest_high > legout_covered_limit
        else:
            lowest_low = stock_data['Low'].iloc[i:entry_index + 1].min()
            return lowest_low < legout_covered_limit
    else:
        crossed = False
        for n in range(i, len(stock_data)):
            if not crossed:
                if (it_is_demand_zone and stock_data['Low'].iloc[n] <= first_legout_half) or \
                   (not it_is_demand_zone and stock_data['High'].iloc[n] >= first_legout_half):
                    crossed = True
            else:
                if (it_is_demand_zone and stock_data['High'].iloc[n] > legout_covered_limit) or \
                   (not it_is_demand_zone and stock_data['Low'].iloc[n] < legout_covered_limit):
                    return True
        return False


def find_patterns(ticker, stock_data, interval_key, max_base_candles, scan_demand_zone_allowed, scan_supply_zone_allowed,reward_value,fresh_zone_allowed,target_zone_allowed,stoploss_zone_allowed,candle_behinde_legin_check_allowed , whitearea_check_allowed,legout_formation_check_allowed, wick_in_legin_allowed, time_validation_allowed,legin_tr_atr_check_allowed, one_legout_count_allowed,three_legout_count_allowed,legout_covered_check_allowed,htf_interval,user_input_zone_distance):
    try:
        patterns = []
        last_legout_high = []  # Initialize here to avoid error
        last_legout_low = [ ] # Intiialize here to avoid error
        
        if len(stock_data) < 3:
            print(f"Not enough stock_data for {ticker}")
            return []

        for i in range(len(stock_data) - 1, 2, -1):
            if scan_demand_zone_allowed and (stock_data['Close'].iloc[i] > stock_data['Open'].iloc[i] and 
                stock_data['TR'].iloc[i] > stock_data['ATR'].iloc[i]):
                if whitearea_check_allowed:
                    white_area_condition = (stock_data['Open'].iloc[i] >= stock_data['Close'].iloc[i - 1] 
                                            if stock_data['Close'].iloc[i - 1] > stock_data['Open'].iloc[i - 1] 
                                            else stock_data['Open'].iloc[i] >= stock_data['Open'].iloc[i - 1])
                else:
                    white_area_condition = True  # If not allowed, treat as true

                # Execute logic only if the white area condition is met
                if white_area_condition:
                   first_legout_open = stock_data['Open'].iloc[i] 
                   first_legout_candle_body = abs(stock_data['Close'].iloc[i] - stock_data['Open'].iloc[i])
                   first_legout_candle_range = (stock_data['High'].iloc[i] - stock_data['Low'].iloc[i])

                   if first_legout_candle_body >= 0.5 * first_legout_candle_range:
                       high_prices = []
                       low_prices = []
                       for base_candles_count in range(1, max_base_candles + 1):
                           base_candles_found = 0
                        
                           legin_candle_index = i - (base_candles_count + 1)
                           legin_candle_body = stock_data['Candle_Body'].iloc[legin_candle_index]
                           legin_candle_range = stock_data['Candle_Range'].iloc[legin_candle_index]
                        
                           for k in range(1, base_candles_count + 1):
                               if (stock_data['ATR'].iloc[i - k] > stock_data['TR'].iloc[i - k] and 
                                   legin_candle_body >= 0.50 * legin_candle_range):
                                
                                   base_candles_found += 1
                                   high_prices.append(stock_data['High'].iloc[i - k])
                                   low_prices.append(stock_data['Low'].iloc[i - k])
                                
                               max_high_price = max(high_prices) if high_prices else None
                               min_low_price = min(low_prices) if low_prices else None
                            
                               if  max_high_price is not None and min_low_price is not None:
                                   actual_base_candle_range = max_high_price - min_low_price
                               actual_legout_candle_range = None
                               first_legout_candle_range_for_one_two_ka_four = (stock_data['High'].iloc[i] - stock_data['Close'].iloc[i-1])    
                               condition_met = False  # Flag to check if any condition was met
                               opposite_color_exist = ((stock_data['Close'].iloc[legin_candle_index] > stock_data['Open'].iloc[legin_candle_index] and 
                                                stock_data['Close'].iloc[legin_candle_index - 1] < stock_data['Open'].iloc[legin_candle_index - 1]) or
                                                (stock_data['Close'].iloc[legin_candle_index] < stock_data['Open'].iloc[legin_candle_index] and 
                                                stock_data['Close'].iloc[legin_candle_index - 1] > stock_data['Open'].iloc[legin_candle_index - 1]))

                               # Check for candle overlap if allowed
                               if candle_behinde_legin_check_allowed and opposite_color_exist:
                                    overlap_condition = is_overlap_less_than_50(stock_data, legin_candle_index)
                               else:
                                    overlap_condition = True  # If not allowed, treat as true
                                   
                               if legout_formation_check_allowed:
                                   legout_formation_condition = (first_legout_open <= stock_data['Close'].iloc[legin_candle_index] + legin_candle_body)
                               else:
                                   legout_formation_condition = True

                               if wick_in_legin_allowed:
                                   wick_in_legin_condition = (stock_data['High'].iloc[legin_candle_index] > stock_data['Close'].iloc[legin_candle_index] and stock_data['Low'].iloc[legin_candle_index] < stock_data['Open'].iloc[legin_candle_index] )
                               else:
                                    wick_in_legin_condition = True 
                               
                               if time_validation_allowed:
                                   time_validation_condition = validate_time_condition(stock_data.index[i], None ,interval_key)                               
                               else :
                                   time_validation_condition = True 


                               if legin_tr_atr_check_allowed:
                                   legin_tr_atr_check_conditon =  (stock_data['TR'].iloc[legin_candle_index] > stock_data['ATR'].iloc[legin_candle_index])
                               else:
                                   legin_tr_atr_check_conditon = True
                       

                               if base_candles_found == base_candles_count:                                   
                                   if not one_legout_count_allowed and not three_legout_count_allowed:
                                      if ( 
                                          legin_candle_range >= 1.5 * actual_base_candle_range and
                                          first_legout_candle_range_for_one_two_ka_four >= 2 * legin_candle_range and 
                                          stock_data['Low'].iloc[i] >= stock_data['Low'].iloc[legin_candle_index] and 
                                       
                                          overlap_condition and legout_formation_condition and wick_in_legin_allowed and time_validation_condition and legin_tr_atr_check_conditon):
                                          condition_met = True  # Set flag if this condition is met

                                      else:  # This is the else part for the if statement above
                                          last_legout_high = []
                                          j = i + 1
                                          while j in range(i + 1, min(i + 3, len(stock_data))) and stock_data['Close'].iloc[j] > stock_data['Open'].iloc[j]:
                                           # Check if j == i + 1
                                              if j == i + 1:
                                                  if (stock_data['Open'].iloc[j] >= 0.10* stock_data['Close'].iloc[i] and 
                                                      stock_data['Low'].iloc[j] >= 0.50 * stock_data['Candle_Range'].iloc[i]):
                                                      last_legout_high.append(stock_data['High'].iloc[j])
        
                                              # Check if j == i + 2
                                              elif j == i + 2:
                                                  if stock_data['Low'].iloc[j] >= stock_data['Low'].iloc[i + 1]:
                                                      last_legout_high.append(stock_data['High'].iloc[j])
              
                                              j += 1

                                          last_legout_high_value = max(last_legout_high) if last_legout_high else None

                                          if last_legout_high_value is not None:
                                              actual_legout_candle_range = last_legout_high_value - stock_data['Close'].iloc[i - 1]

                                              if (legin_candle_range >= 1.5 * actual_base_candle_range and 
                                                  actual_legout_candle_range >= 2 * legin_candle_range and
                                                  stock_data['Low'].iloc[i] >= stock_data['Low'].iloc[legin_candle_index] and 
                                                  overlap_condition and legout_formation_condition and wick_in_legin_allowed and time_validation_condition and legin_tr_atr_check_conditon):
                      
                                                  condition_met = True  # Set flag if this condition is met
                                                      
                                   else:
                                       # If the one_legout_count_allowed checkbox is checked
                                       if one_legout_count_allowed:
                                           if (legin_candle_range >= 1.5 * actual_base_candle_range and
                                               first_legout_candle_range_for_one_two_ka_four >= 2 * legin_candle_range and 
                                               stock_data['Low'].iloc[i] >= stock_data['Low'].iloc[legin_candle_index] and 
                                               overlap_condition and legout_formation_condition and 
                                               wick_in_legin_allowed and time_validation_condition and 
                                               legin_tr_atr_check_conditon):
                                               condition_met = True  # Set flag if this condition is met

                                       # If the three_legout_count_allowed checkbox is checked
                                       if three_legout_count_allowed and not condition_met:
                                           last_legout_high = []
                                           j = i + 1
                                           while j in range(i + 1, min(i + 3, len(stock_data))) and stock_data['Close'].iloc[j] > stock_data['Open'].iloc[j]:
                                               # Check if j == i + 1
                                               if j == i + 2:
                                                   if (stock_data['Open'].iloc[i+1] >= 0.10 * stock_data['Close'].iloc[i] and 
                                                       stock_data['Low'].iloc[i+1] >= 0.50 * stock_data['Candle_Range'].iloc[i] and
                                                       stock_data['Low'].iloc[j] >= stock_data['Low'].iloc[i + 1] ):
                                                       last_legout_high.append(stock_data['High'].iloc[j])
                                               j += 1
                                           last_legout_high_value = max(last_legout_high) if last_legout_high else None
 
                                           if last_legout_high_value is not None:
                                               actual_legout_candle_range = last_legout_high_value - stock_data['Close'].iloc[i - 1]
 
                                               if (legin_candle_range >= 1.5 * actual_base_candle_range and 
                                                   actual_legout_candle_range >= 2 * legin_candle_range and
                                                   stock_data['Low'].iloc[i] >= stock_data['Low'].iloc[legin_candle_index] and 
                                                   overlap_condition and legout_formation_condition and wick_in_legin_allowed and time_validation_condition and legin_tr_atr_check_conditon):
                       
                                                   condition_met = True  # Set flag if this condition is met                               
                             
                               if condition_met:
                                   if interval_key in ('1 Day','1 Week','1 Month'):
                                       legin_date = stock_data.index[legin_candle_index].strftime('%Y-%m-%d')
                                       legout_date = stock_data.index[i].strftime('%Y-%m-%d')
                                   else:
                                       legin_date = stock_data.index[legin_candle_index].strftime('%Y-%m-%d %H:%M:%S')
                                       legout_date = stock_data.index[i].strftime('%Y-%m-%d %H:%M:%S')
                                
                                   if actual_legout_candle_range is not None:
                                       legout_candle_range = actual_legout_candle_range
                                   else:
                                       legout_candle_range = first_legout_candle_range_for_one_two_ka_four


                                   entry_occurred = False
                                   target_hit = False
                                   stop_loss_hit = False
                                   entry_date = None
                                   entry_index = None
                                   exit_date = None
                                   exit_index = None
                                   Zone_status = None
                                   total_risk = max_high_price - min_low_price
                                   minimum_target = (total_risk * reward_value) + max_high_price                  
                                   start_index = j+1 if last_legout_high else i + 1


                                   for m in range(start_index, len(stock_data)):
                                       if not entry_occurred:
                                           # Check if the entry condition is met
                                           if stock_data['Low'].iloc[m] <= max_high_price:
                                               entry_occurred = True
                                               entry_index = m
                                               entry_date = stock_data.index[m]
   
                                               # Check if the low and high of the current candle exceed the limits
                                               if stock_data['Low'].iloc[m] < min_low_price:
                                                   stop_loss_hit = True
                                                   exit_index = m
                                                   exit_date = stock_data.index[m]
                                                   Zone_status = 'Stop loss'
                                                   break  # Exit the loop after stop-loss is hit
                                               elif stock_data['High'].iloc[m] >= minimum_target:
                                                   target_hit = True
                                                   exit_index = m
                                                   exit_date = stock_data.index[m]
                                                   Zone_status = 'Target'
                                                   break  # Exit the loop after target is hit
                                           elif min(stock_data['Low'].iloc[start_index:]) > max_high_price:
                                                Zone_status = 'Fresh'
                                       
                                       else:
                                           # After entry, check if price hits stop-loss or minimum target
                                           if stock_data['Low'].iloc[m] < min_low_price:
                                               stop_loss_hit = True
                                               exit_index = m
                                               exit_date = stock_data.index[m]
                                               Zone_status = 'Stop loss'
                                               break  # Exit the loop after stop-loss is hit
                                           elif stock_data['High'].iloc[m] >= minimum_target:
                                               target_hit = True
                                               exit_index = m
                                               exit_date = stock_data.index[m]
                                               Zone_status = 'Target'
                                               break  # Exit the loop after target is hit
                                   if  legout_covered_check_allowed :
                                       it_is_demand_zone = True
                                       legout_covered_check_condition = check_legout_covered(it_is_demand_zone, stock_data, i, entry_index, total_risk, reward_value, first_legout_candle_range, max_high_price)       
                                   else:
                                       legout_covered_check_condition = True
                                       
                                   if time_validation_allowed and entry_date is not None:
                                       time_validation_condition = validate_time_condition(stock_data.index[i], entry_date, interval_key)
                                   else :
                                       time_validation_condition = True                                 
                                   # time_in_exit = exit_index - entry_index                                
                                   latest_closing_price = round(stock_data['Close'].iloc[-1], 2)
                                   zone_distance = (math.floor(latest_closing_price) - max(high_prices)) / max(high_prices) * 100
                                                                   
                                   if ((fresh_zone_allowed and Zone_status == 'Fresh') or \
                                      (target_zone_allowed and Zone_status == 'Target') or \
                                      (stoploss_zone_allowed and Zone_status == 'Stop loss')) and time_validation_condition and legout_covered_check_condition and zone_distance <= user_input_zone_distance:
                                      
                                      Pattern_name_is = 'DZ(DBR)' if stock_data['Open'].iloc[legin_candle_index] > stock_data['Close'].iloc[legin_candle_index] else 'DZ(RBR)'
                                      legin_base_legout_ranges = f"{round(legin_candle_range)}:{round(actual_base_candle_range)}:{round(legout_candle_range)}"
                                      ohlc_data = capture_ohlc_data(stock_data, exit_index, i)                                   
                                      pulse_check_start_date = pd.Timestamp(entry_date) if entry_date is not None else pd.Timestamp.now()
                                      #pulse_details,trend_label = check_golden_crossover(stock_data_htf, pulse_check_start_date)       
                                          
                                      patterns.append({
                                           'Symbol': ticker, 
                                           'Time_frame': interval_key,
                                           'Pulse_details': " ", 
                                           'Trend': " ",
                                           'Zone_status':Zone_status,
                                           'Zone_Type' : Pattern_name_is,
                                           'Entry_Price':max_high_price,
                                           'Stop_loss': min_low_price,
                                           'Target': minimum_target,
                                           'Entry_date':entry_date,
                                           'Exit_date':exit_date,
                                           'Exit_index' :exit_index ,  
                                           'Entry_index' :entry_index ,  
                                           'Zone_Distance': zone_distance.round(2),
                                           'legin_date': legin_date,
                                           'base_count': base_candles_found,
                                           'legout_date': legout_date,
                                           'legin:base:legout_ranges': legin_base_legout_ranges,
                                           'OHLC_Data': ohlc_data,
                                           'Close_price': latest_closing_price
                                       })

            if scan_supply_zone_allowed and (stock_data['Open'].iloc[i] > stock_data['Close'].iloc[i] and 
                                              stock_data['TR'].iloc[i] > stock_data['ATR'].iloc[i]):

                # Check for white area condition if allowed
                if whitearea_check_allowed:
                    white_area_condition_supply = (stock_data['Open'].iloc[i] <= stock_data['Close'].iloc[i - 1] 
                                                    if stock_data['Close'].iloc[i - 1] < stock_data['Open'].iloc[i - 1] 
                                                    else stock_data['Open'].iloc[i] <= stock_data['Open'].iloc[i - 1])
                else:
                    white_area_condition_supply = True  # If not allowed, treat as true

                if white_area_condition_supply:
                    first_legout_open = stock_data['Open'].iloc[i]
                    first_legout_candle_body = abs(stock_data['Close'].iloc[i] - stock_data['Open'].iloc[i])
                    first_legout_candle_range = (stock_data['High'].iloc[i] - stock_data['Low'].iloc[i])
                    
                    if first_legout_candle_body >= 0.5 * first_legout_candle_range:
                        high_prices = []
                        low_prices = []
                        for base_candles_count in range(1, max_base_candles + 1):
                            base_candles_found = 0
                        
                            legin_candle_index = i - (base_candles_count + 1)
                            legin_candle_body = stock_data['Candle_Body'].iloc[legin_candle_index]
                            legin_candle_range = stock_data['Candle_Range'].iloc[legin_candle_index]
                            
                            for k in range(1, base_candles_count + 1):
                                if (stock_data['ATR'].iloc[i - k] > stock_data['TR'].iloc[i - k] and 
                                    legin_candle_body >= 0.50 * legin_candle_range):
                                
                                    base_candles_found += 1
                                    high_prices.append(stock_data['High'].iloc[i - k])
                                    low_prices.append(stock_data['Low'].iloc[i - k])
                                
                                max_high_price = max(high_prices) if high_prices else None
                                min_low_price = min(low_prices) if low_prices else None
                            
                                if max_high_price is not None and min_low_price is not None:
                                    actual_base_candle_range = max_high_price - min_low_price
                                actual_legout_candle_range = None
                                first_legout_candle_range_for_one_two_ka_four = (stock_data['Close'].iloc[i-1] - stock_data['Low'].iloc[i])    
                                condition_met = False  # Flag to check if any condition was met

                                opposite_color_exist = ((stock_data['Close'].iloc[legin_candle_index] > stock_data['Open'].iloc[legin_candle_index] and 
                                                stock_data['Close'].iloc[legin_candle_index - 1] < stock_data['Open'].iloc[legin_candle_index - 1]) or
                                                (stock_data['Close'].iloc[legin_candle_index] < stock_data['Open'].iloc[legin_candle_index] and 
                                                stock_data['Close'].iloc[legin_candle_index - 1] > stock_data['Open'].iloc[legin_candle_index - 1]))
                                
                                if candle_behinde_legin_check_allowed and opposite_color_exist:
                                    overlap_condition = is_overlap_less_than_50(stock_data, legin_candle_index)
                                else:
                                    overlap_condition = True  # If not allowed, treat as true

                                if legout_formation_check_allowed:
                                   legout_formation_condition = (first_legout_open >= stock_data['Close'].iloc[legin_candle_index] - legin_candle_body)
                                else:
                                   legout_formation_condition = True  
                                   
                                if wick_in_legin_allowed:
                                   wick_in_legin_condition = (stock_data['High'].iloc[legin_candle_index] > stock_data['Open'].iloc[legin_candle_index] and stock_data['Low'].iloc[legin_candle_index] < stock_data['Close'].iloc[legin_candle_index])
                                else :
                                   wick_in_legin_allowed = True 
                                if time_validation_allowed:
                                   time_validation_condition = validate_time_condition(stock_data.index[i], None, interval_key)
                               
                                else :
                                   time_validation_condition = True 
                                if legin_tr_atr_check_allowed:
                                   legin_tr_atr_check_conditon =  (stock_data['TR'].iloc[legin_candle_index] > stock_data['ATR'].iloc[legin_candle_index])
                                else:
                                   legin_tr_atr_check_conditon = True
                                   
                                if base_candles_found == base_candles_count:
                                   if not one_legout_count_allowed and not three_legout_count_allowed:
                                    
                                     if (legin_candle_range >= 1.5 * actual_base_candle_range and
                                        first_legout_candle_range_for_one_two_ka_four >= 2 * legin_candle_range and 
                                    
                                        stock_data['High'].iloc[i] <= stock_data['High'].iloc[legin_candle_index] and
                                        overlap_condition and legout_formation_condition and wick_in_legin_allowed and time_validation_allowed and legin_tr_atr_check_conditon):
                                        
                                        condition_met = True  # Set flag if this condition is met
                                     else:  # This is the else part for the if statement above
                                        last_legout_low = []
                                        j = i + 1
                                        while j in range(i + 1, min(i + 3, len(stock_data))) and stock_data['Open'].iloc[j] > stock_data['Close'].iloc[j]:
                                            # Check if j == i + 1
                                            if j == i + 1:
                                                if (stock_data['Open'].iloc[j] <= 0.10* stock_data['Close'].iloc[i] and 
                                                    stock_data['High'].iloc[j] <= 0.50 * stock_data['Candle_Range'].iloc[i]):
                                                    last_legout_low.append(stock_data['Low'].iloc[j])
            
                                                # Check if j == i + 2
                                                elif j == i + 2:
                                                    if stock_data['High'].iloc[j] <= stock_data['High'].iloc[i + 1]:
                                                        last_legout_low.append(stock_data['Low'].iloc[j])
            
                                            j += 1

                                        last_legout_low_value = min(last_legout_low) if last_legout_low else None

                                        if last_legout_low_value is not None:
                                            actual_legout_candle_range = abs(last_legout_low_value - stock_data['Close'].iloc[i - 1])

                                            if (legin_candle_range >= 1.5 * actual_base_candle_range and 
                                                actual_legout_candle_range >= 2 * legin_candle_range and
                                                stock_data['High'].iloc[i] <= stock_data['High'].iloc[legin_candle_index] and 
                                                overlap_condition and legout_formation_condition and wick_in_legin_allowed and time_validation_allowed and legin_tr_atr_check_conditon ):
                
                                                condition_met = True  # Set flag if this condition is met
                                   else:
                                       # If the one_legout_count_allowed checkbox is checked
                                       if one_legout_count_allowed:
                                          if (legin_candle_range >= 1.5 * actual_base_candle_range and
                                             first_legout_candle_range_for_one_two_ka_four >= 2 * legin_candle_range and 
                                    
                                             stock_data['High'].iloc[i] <= stock_data['High'].iloc[legin_candle_index] and
                                             overlap_condition and legout_formation_condition and wick_in_legin_allowed and time_validation_allowed and legin_tr_atr_check_conditon):
                                        
                                             condition_met = True  # Set flag if this condition is met

                                       
                                       if three_legout_count_allowed and not condition_met :
                                           last_legout_low = []
                                           j = i + 1
                                           while j in range(i + 1, min(i + 3, len(stock_data))) and stock_data['Open'].iloc[j] > stock_data['Close'].iloc[j]:
                                               # Check if j == i + 1
                                               if j == i + 2:
                                                   if (stock_data['Open'].iloc[j] <= 0.10* stock_data['Close'].iloc[i] and 
                                                       stock_data['High'].iloc[j] <= 0.50 * stock_data['Candle_Range'].iloc[i] and 
                                                       stock_data['High'].iloc[j] <= stock_data['High'].iloc[i + 1]) :
                                                       last_legout_low.append(stock_data['Low'].iloc[j])
            
                                               j += 1

                                           last_legout_low_value = min(last_legout_low) if last_legout_low else None

                                           if last_legout_low_value is not None:
                                               actual_legout_candle_range = abs(last_legout_low_value - stock_data['Close'].iloc[i - 1])
                                               if (legin_candle_range >= 1.5 * actual_base_candle_range and 
                                                   actual_legout_candle_range >= 2 * legin_candle_range and
                                                   stock_data['High'].iloc[i] <= stock_data['High'].iloc[legin_candle_index] and 
                                                   overlap_condition and legout_formation_condition and wick_in_legin_allowed and time_validation_allowed and legin_tr_atr_check_conditon ):
                
                                                   condition_met = True  # Set flag if this condition is met
                                           
                                # Code block to execute if any condition was met
                                if condition_met:
                                    if interval_key in ('1 Day','1 Week','1 Month') :
                                        legin_date = stock_data.index[legin_candle_index].strftime('%Y-%m-%d')
                                        legout_date = stock_data.index[i].strftime('%Y-%m-%d')
                                    else:
                                        legin_date = stock_data.index[legin_candle_index].strftime('%Y-%m-%d %H:%M:%S')
                                        legout_date = stock_data.index[i].strftime('%Y-%m-%d %H:%M:%S')
                                
                                    if actual_legout_candle_range is not None:
                                        legout_candle_range = actual_legout_candle_range
                                    else:
                                        legout_candle_range = first_legout_candle_range_for_one_two_ka_four

                                    entry_occurred = False
                                    target_hit = False
                                    stop_loss_hit = False
                                    entry_date = None
                                    entry_index = None
                                    exit_date = None
                                    exit_index = None
                                    Zone_status = None
                                    total_risk = max_high_price - min_low_price
                                    minimum_target = min_low_price - (total_risk * reward_value)                   
                                    start_index = j+1 if last_legout_low else i + 1

                                    for m in range(start_index, len(stock_data)):
                                        if not entry_occurred:
                                            # Check if the entry condition is met
                                            if stock_data['High'].iloc[m] >= min_low_price:
                                                entry_occurred = True
                                                entry_index = m
                                                entry_date = stock_data.index[m]

                                                # Check if the low and high of the current candle exceed the limits
                                                if stock_data['High'].iloc[m] > max_high_price:
                                                    stop_loss_hit = True
                                                    exit_index = m
                                                    exit_date = stock_data.index[m]
                                                    Zone_status = 'Stop loss'
                                                    break  # Exit the loop after stop-loss is hit
                                                elif stock_data['Low'].iloc[m] <= minimum_target:
                                                    target_hit = True
                                                    exit_index = m
                                                    exit_date = stock_data.index[m]
                                                    Zone_status = 'Target'
                                                    break  # Exit the loop after target is hit
                                            elif max(stock_data['High'].iloc[start_index:]) < min_low_price:
                                                 Zone_status = 'Fresh'
                                        else:
                                            # After entry, check if price hits stop-loss or minimum target
                                            if stock_data['High'].iloc[m] > max_high_price:
                                                stop_loss_hit = True
                                                exit_index = m
                                                exit_date = stock_data.index[m]
                                                Zone_status = 'Stop loss'
                                                break  # Exit the loop after stop-loss is hit
                                            elif stock_data['Low'].iloc[m] <= minimum_target:
                                                target_hit = True
                                                exit_index = m
                                                exit_date = stock_data.index[m]
                                                Zone_status = 'Target'
                                                break  # Exit the loop after target is hit
                                    if  legout_covered_check_allowed :
                                        it_is_demand_zone = False
                                        legout_covered_check_condition = check_legout_covered(it_is_demand_zone, stock_data, i, entry_index, total_risk, reward_value, first_legout_candle_range, min_low_price)       
                                    else:
                                        legout_covered_check_condition = True
                                    
                                    if time_validation_allowed and entry_date is not None:
                                       time_validation_condition = validate_time_condition(stock_data.index[i], entry_date, interval_key)
                                    else :
                                       time_validation_condition = True     
                                    latest_closing_price = round(stock_data['Close'].iloc[-1], 2)
                                    zone_distance = (min(low_prices) - math.floor(latest_closing_price)) / min(low_prices) * 100
                                                                    
                                    if ((fresh_zone_allowed and Zone_status == 'Fresh') or \
                                       (target_zone_allowed and Zone_status == 'Target') or \
                                       (stoploss_zone_allowed and Zone_status == 'Stop loss')) and time_validation_condition and legout_covered_check_condition and zone_distance <= user_input_zone_distance:
                                           
                                       Pattern_name_is = 'SZ(RBD)' if stock_data['Close'].iloc[legin_candle_index] > stock_data['Open'].iloc[legin_candle_index] else 'SZ(DBD)'
                                       legin_base_legout_ranges = f"{round(legin_candle_range, 2)}:{round(actual_base_candle_range, 2)}:{round(legout_candle_range, 2)}"
                                    
                                       ohlc_data = capture_ohlc_data(stock_data, exit_index, i)
                                    
                                       pulse_check_start_date = pd.Timestamp(entry_date) if entry_date is not None else pd.Timestamp.now()
                                       #pulse_details,trend_label = check_golden_crossover(stock_data_htf, pulse_check_start_date)
                                           
                                       patterns.append({
                                            'Symbol': ticker, 
                                            'Time_frame':interval_key,                                       
                                            'Pulse_details': " ", 
                                            'Trend':" ",                                       
                                            'Zone_status':Zone_status,
                                            'Zone_Type' : Pattern_name_is,
                                            'Entry_Price':max_high_price,
                                            'Stop_loss': min_low_price,
                                            'Target': minimum_target,
                                            'Entry_date':entry_date,
                                            'Exit_date':exit_date,
                                            'Exit_index' :exit_index ,  
                                            'Entry_index' :entry_index ,                                                                            
                                            'Zone_Distance': zone_distance.round(2),
                                            'legin_date': legin_date,
                                            'base_count': base_candles_found,
                                            'legout_date': legout_date,
                                            'legin:base:legout_ranges': legin_base_legout_ranges,
                                            'OHLC_Data': ohlc_data,
                                            'Close_price': latest_closing_price
                                        })
                              
        return patterns
    except Exception as e:
        print(f"Error processing {ticker}: {e}")
        return []


# Initialize TvDatafeed with your TradingView credentials
tv = TvDatafeed('AKTradingWithSL', 'bulky@001122')
#st.sidebar.title("😊 Welcome to demand - supply zone scanner")

st.sidebar.title("📘 Scanner Manual")

st.sidebar.info("""
1. **Script select kare**: sbse pahle script select kare jiske liye aap zone scan karna chaahte hain . 
2. **boring candles**: zone me borig candle yani base candle maximum kitna hoga chahaiye yah darj kare (default 1 hai ).
3. **zone distance**: zone distance ka matlab current price aur zone ke entry price ke beech jo % ka distace ya gap hai vo kitna hoga chahiye , jitna kam distance hoga , price zone ke utna najdik hoga.
4. **Time Framee** : fir iske baad ab aapko time frame select karna hoga ki aap kis time frame ke liye zone scan karna chaahte hain , ek bar me jitna kam time frame ke zone scan karege utna jaldi scannig hoga , jyada time frame select karege to jyada time lagega .
5. **zone status and zone type** : zone status and zone type ka matlab yah hai ki aap fresh zone chahte hai ya stoploss , target wale , ab iske baad zone ka type kaisa hoga yani demand zone ya supply zone , ye selection aap zone status and zone tupe se kar sakte hai
6.**zone validation**: aap aap strong zone chaahte hai to iske liye aapko kuchh validation lagane ki jaruat ho skti hai, zone validation me ham kuch validation diye hain , jiske aadhar par aap zone filter kar sakte hain , 
7. **Scan period days**: iska matlab yah hai ki aap aaj ke din se lekar pichhle kitne din tak kaa zone scan karna chahte hain .
""")

st.markdown(f"<h3 style=\"text-align: center;\"> 😊 Welcome to demand - supply  zone scanner </h3>", unsafe_allow_html=True)

# Define stock options similar to the JavaScript example
stock_options = {
    "Custom Symbol": [],
    "FnO Stocks": ['COFORGE', 'FEDERALBNK', 'OBEROIRLTY', 'CUMMINSIND', 'EICHERMOT', 'M&M', 'RAMCOCEM', 'ULTRACEMCO', 'ABFRL', 'GODREJPROP', 'PAGEIND', 'PETRONET', 'BSOFT', 'ACC', 'LT', 'GRASIM', 'SHREECEM', 'ABB', 'CANFINHOME', 'TRENT', 'HDFCLIFE', 'GUJGASLTD', 'LTTS', 'SBIN', 'MRF', 'ASHOKLEY', 'SIEMENS', 'MARUTI', 'CONCOR', 'MOTHERSON', 'TATACOMM', 'NTPC', 'ITC', 'APOLLOHOSP', 'DALBHARAT', 'BAJFINANCE', 'MGL', 'BAJAJFINSV', 'ADANIPORTS', 'MPHASIS', 'GODREJCP', 'NMDC', 'ADANIENT', 'ICICIGI', 'LALPATHLAB', 'TORNTPHARM', 'LUPIN', 'PFC', 'HINDUNILVR', 'IRCTC', 'ICICIBANK', 'PNB', 'IPCALAB', 'SBILIFE', 'KOTAKBANK', 'DABUR', 'INDIAMART', 'CHOLAFIN', 'LTIM', 'SUNTV', 'GAIL', 'NESTLEIND', 'BHARATFORG', 'BANKBARODA', 'CANBK', 'TATAPOWER', 'DRREDDY', 'HEROMOTOCO', 'LAURUSLABS', 'M&MFIN', 'HAL', 'INDIGO', 'UPL', 'INDUSINDBK', 'TITAN', 'UBL', 'GNFC', 'MFSL', 'SUNPHARMA', 'BOSCHLTD', 'AXISBANK', 'JUBLFOOD', 'JINDALSTEL', 'AUROPHARMA', 'TATACONSUM', 'PIDILITIND', 'VOLTAS', 'SYNGENE', 'AMBUJACEM', 'RECLTD', 'ASTRAL', 'ASIANPAINT', 'BATAINDIA', 'DLF', 'TATAMOTORS', 'INDHOTEL', 'IGL', 'BEL', 'NAVINFLUOR', 'RELIANCE', 'CIPLA', 'ESCORTS', 'INFY', 'BHARTIARTL', 'BAJAJ-AUTO', 'TATASTEEL', 'METROPOLIS', 'ALKEM', 'BRITANNIA', 'COLPAL', 'PVRINOX', 'ICICIPRULI', 'MUTHOOTFIN', 'EXIDEIND', 'TCS', 'LICHSGFIN', 'Time frame', 'IOC', 'OFSS', 'TVSMOTOR', 'INDUSTOWER', 'BALKRISIND', 'TECHM', 'COALINDIA', 'BALRAMCHIN', 'BIOCON', 'NAUKRI', 'SBICARD', 'BERGEPAINT', 'INDIACEM', 'JSWSTEEL', 'IDFCFIRSTB', 'HDFCBANK', 'HAVELLS', 'ABCAPITAL', 'HDFCAMC', 'DEEPAKNTR', 'PEL', 'BPCL', 'RBLBANK', 'ZYDUSLIFE', 'AUBANK', 'MANAPPURAM', 'PIIND', 'SAIL', 'POWERGRID', 'WIPRO', 'DIVISLAB', 'COROMANDEL', 'HCLTECH', 'ATUL', 'POLYCAB', 'SRF', 'ABBOTINDIA', 'BHEL', 'AARTIIND', 'IEX', 'MCX', 'HINDALCO', 'HINDPETRO', 'BANDHANBNK', 'CUB', 'IDFC', 'TATACHEM', 'MARICO', 'IDEA', 'ONGC', 'GRANULES', 'DIXON', 'JKCEMENT', 'APOLLOTYRE', 'GMRINFRA', 'GLENMARK', 'CHAMBLFERT', 'PERSISTENT', 'CROMPTON', 'SHRIRAMFIN', 'HINDCOPPER', 'NATIONALUM', 'VEDL'],
    "Intraday Stocks": ['TATASTEEL', 'MOTHERSON', 'NYKAA', 'NMDC', 'GAIL', 'BANKBARODA', 'ZOMATO', 'ASHOKLEY', 'BEL', 'JIOFIN', 'ONGC', 'POWERGRID', 'BPCL', 'PETRONET', 'NTPC', 'HINDPETRO', 'TATAPOWER', 'INDUSTOWER', 'VEDL', 'ITC', 'COALINDIA', 'PFC', 'KALYANKJIL', 'RECLTD', 'DABUR', 'MARICO', 'INDHOTEL', 'CGPOWER', 'HINDALCO', 'SBICARD', 'HDFCLIFE', 'OIL', 'JSL', 'SBIN', 'MAXHEALTH', 'JSWSTEEL', 'CONCOR', 'JINDALSTEL', 'TATAMOTORS', 'UNOMINDA', 'AXISBANK', 'TATACONSUM', 'ICICIBANK', 'INDUSINDBK', 'CHOLAFIN', 'UNITDSPR', 'GODREJCP', 'ADANIPORTS', 'VBL', 'AUROPHARMA', 'BHARATFORG', 'BHARTIARTL', 'TECHM', 'HDFCBANK', 'CIPLA', 'TORNTPOWER', 'VOLTAS', 'HCLTECH', 'COROMANDEL', 'POLICYBZR', 'OBEROIRLTY', 'KOTAKBANK', 'PRESTIGE', 'KPITTECH', 'SUNPHARMA', 'SBILIFE', 'HAVELLS', 'ASTRAL', 'INFY', 'TATACOMM', 'ICICIGI', 'LUPIN', 'SRF', 'GRASIM', 'HINDUNILVR', 'M&M', 'TVSMOTOR', 'BALKRISIND', 'GODREJPROP', 'RELIANCE', 'MPHASIS', 'ASIANPAINT', 'SHRIRAMFIN', 'TITAN', 'COLPAL', 'LT', 'CUMMINSIND', 'PHOENIXLTD'],
    "Nifty50stocks": ['RELIANCE','TCS','HDFCBANK','BHARTIARTL','ICICIBANK','INFY','SBIN','HINDUNILVR','LICI','ITC','LT','HCLTECH','BAJFINANCE','SUNPHARMA','NTPC','TATAMOTORS','MARUTI','AXISBANK','KOTAKBANK','ONGC','M_M','DMART','ADANIENT','ULTRACEMCO','TITAN','BAJAJ_AUTO','ASIANPAINT','POWERGRID','ADANIGREEN','ADANIPORTS','BAJAJFINSV','COALINDIA','HAL','WIPRO','TRENT','ADANIPOWER','NESTLEIND','ZOMATO','SIEMENS','IOC','JSWSTEEL','JIOFIN','DLF','VBL','IRFC','BEL','HINDZINC','INDIGO','LTIM','TATASTEEL'],
    "Nifty100stocks": ['RELIANCE','TCS','HDFCBANK','BHARTIARTL','ICICIBANK','INFY','SBIN','HINDUNILVR','LICI','ITC','LT','HCLTECH','BAJFINANCE','SUNPHARMA','NTPC','TATAMOTORS','MARUTI','AXISBANK','KOTAKBANK','ONGC','M_M','DMART','ADANIENT','ULTRACEMCO','TITAN','BAJAJ_AUTO','ASIANPAINT','POWERGRID','ADANIGREEN','ADANIPORTS','BAJAJFINSV','COALINDIA','HAL','WIPRO','TRENT','ADANIPOWER','NESTLEIND','ZOMATO','SIEMENS','IOC','JSWSTEEL','JIOFIN','DLF','VBL','IRFC','BEL','HINDZINC','INDIGO','LTIM','TATASTEEL','GRASIM','SBILIFE','VEDL','ABB','PFC','PIDILITIND','TECHM','HINDALCO','AMBUJACEM','HDFCLIFE','BRITANNIA','GODREJCP','BPCL','DIVISLAB','RECLTD','GAIL','TATAPOWER','MOTHERSON','SHRIRAMFIN','CHOLAFIN','CIPLA','EICHERMOT','TVSMOTOR','JSWENERGY','LODHA','HAVELLS','BANKBARODA','BAJAJHLDNG','PNB','HEROMOTOCO','TATACONSUM','ADANIENSOL','DABUR','INDUSINDBK','TORNTPHARM','CGPOWER','INDUSTOWER','UNITDSPR','IOB','SUZLON','RVNL','DRREDDY','ZYDUSLIFE','ICICIPRULI','ICICIGI','JINDALSTEL','CUMMINSIND','LUPIN','BOSCHLTD','APOLLOHOSP'],
    "Nifty200stocks": ['RELIANCE','TCS','HDFCBANK','BHARTIARTL','ICICIBANK','INFY','SBIN','HINDUNILVR','LICI','ITC','LT','HCLTECH','BAJFINANCE','SUNPHARMA','NTPC','TATAMOTORS','MARUTI','AXISBANK','KOTAKBANK','ONGC','M_M','DMART','ADANIENT','ULTRACEMCO','TITAN','BAJAJ_AUTO','ASIANPAINT','POWERGRID','ADANIGREEN','ADANIPORTS','BAJAJFINSV','COALINDIA','HAL','WIPRO','TRENT','ADANIPOWER','NESTLEIND','ZOMATO','SIEMENS','IOC','JSWSTEEL','JIOFIN','DLF','VBL','IRFC','BEL','HINDZINC','INDIGO','LTIM','TATASTEEL','GRASIM','SBILIFE','VEDL','ABB','PFC','PIDILITIND','TECHM','HINDALCO','AMBUJACEM','HDFCLIFE','BRITANNIA','GODREJCP','BPCL','DIVISLAB','RECLTD','GAIL','TATAPOWER','MOTHERSON','SHRIRAMFIN','CHOLAFIN','CIPLA','EICHERMOT','TVSMOTOR','JSWENERGY','LODHA','HAVELLS','BANKBARODA','BAJAJHLDNG','PNB','HEROMOTOCO','TATACONSUM','ADANIENSOL','DABUR','INDUSINDBK','TORNTPHARM','CGPOWER','INDUSTOWER','UNITDSPR','IOB','SUZLON','RVNL','DRREDDY','ZYDUSLIFE','ICICIPRULI','ICICIGI','JINDALSTEL','CUMMINSIND','LUPIN','BOSCHLTD','APOLLOHOSP','POLYCAB','NAUKRI','GMRINFRA','COLPAL','OFSS','SOLARINDS','INDHOTEL','OIL','IDBI','MANKIND','CANBK','NHPC','HDFCAMC','UNIONBANK','MAXHEALTH','TORNTPOWER','BHEL','SHREECEM','AUROPHARMA','MARICO','IDEA','ATGL','HINDPETRO','MAZDOCK','DIXON','POLICYBZR','MUTHOOTFIN','PRESTIGE','GODREJPROP','PERSISTENT','TIINDIA','SBICARD','BHARATFORG','YESBANK','ALKEM','IRCTC','BERGEPAINT','KALYANKJIL','SRF','LINDEINDIA','PIIND','ASHOKLEY','GICRE','JSWINFRA','SUPREMEIND','INDIANB','OBEROIRLTY','FACT','PATANJALI','VOLTAS','NMDC','THERMAX','JSL','PHOENIXLTD','SCHAEFFLER','UNOMINDA','ABCAPITAL','ABBOTINDIA','BALKRISIND','UCOBANK','LTTS','NYKAA','MRF','MPHASIS','TATACOMM','CONCOR','SUNDARMFIN','POWERINDIA','IDFCFIRSTB','UBL','AUBANK','PGHH','SAIL','BSE','CENTRALBK','ASTRAL','COROMANDEL','SJVN','BANKINDIA','PETRONET','HUDCO','PAGEIND','TATAELXSI','FLUOROCHEM','GLAXO','KPITTECH','ACC','GLENMARK','MOTILALOFS','AWL','COFORGE','UPL','COCHINSHIP','FEDERALBNK','FORTIS','SONACOMS','JUBLFOOD','LTF','HONAUT','BIOCON'],
    "Nifty500stocks": ['RELIANCE','TCS','HDFCBANK','BHARTIARTL','ICICIBANK','INFY','SBIN','HINDUNILVR','LICI','ITC','LT','HCLTECH','BAJFINANCE','SUNPHARMA','NTPC','TATAMOTORS','MARUTI','AXISBANK','KOTAKBANK','ONGC','M_M','DMART','ADANIENT','ULTRACEMCO','TITAN','BAJAJ_AUTO','ASIANPAINT','POWERGRID','ADANIGREEN','ADANIPORTS','BAJAJFINSV','COALINDIA','HAL','WIPRO','TRENT','ADANIPOWER','NESTLEIND','ZOMATO','SIEMENS','IOC','JSWSTEEL','JIOFIN','DLF','VBL','IRFC','BEL','HINDZINC','INDIGO','LTIM','TATASTEEL','GRASIM','SBILIFE','VEDL','ABB','PFC','PIDILITIND','TECHM','HINDALCO','AMBUJACEM','HDFCLIFE','BRITANNIA','GODREJCP','BPCL','DIVISLAB','RECLTD','GAIL','TATAPOWER','MOTHERSON','SHRIRAMFIN','CHOLAFIN','CIPLA','EICHERMOT','TVSMOTOR','JSWENERGY','LODHA','HAVELLS','BANKBARODA','BAJAJHLDNG','PNB','HEROMOTOCO','TATACONSUM','ADANIENSOL','DABUR','INDUSINDBK','TORNTPHARM','CGPOWER','INDUSTOWER','UNITDSPR','IOB','SUZLON','RVNL','DRREDDY','ZYDUSLIFE','ICICIPRULI','ICICIGI','JINDALSTEL','CUMMINSIND','LUPIN','BOSCHLTD','APOLLOHOSP','POLYCAB','NAUKRI','GMRINFRA','COLPAL','OFSS','SOLARINDS','INDHOTEL','OIL','IDBI','MANKIND','CANBK','NHPC','HDFCAMC','UNIONBANK','MAXHEALTH','TORNTPOWER','BHEL','SHREECEM','AUROPHARMA','MARICO','IDEA','ATGL','HINDPETRO','MAZDOCK','DIXON','POLICYBZR','MUTHOOTFIN','PRESTIGE','GODREJPROP','PERSISTENT','TIINDIA','SBICARD','BHARATFORG','YESBANK','ALKEM','IRCTC','BERGEPAINT','KALYANKJIL','SRF','LINDEINDIA','PIIND','ASHOKLEY','GICRE','JSWINFRA','SUPREMEIND','INDIANB','OBEROIRLTY','FACT','PATANJALI','VOLTAS','NMDC','THERMAX','JSL','PHOENIXLTD','SCHAEFFLER','UNOMINDA','ABCAPITAL','ABBOTINDIA','BALKRISIND','UCOBANK','LTTS','NYKAA','MRF','MPHASIS','TATACOMM','CONCOR','SUNDARMFIN','POWERINDIA','IDFCFIRSTB','UBL','AUBANK','PGHH','SAIL','BSE','CENTRALBK','ASTRAL','COROMANDEL','SJVN','BANKINDIA','PETRONET','HUDCO','PAGEIND','TATAELXSI','FLUOROCHEM','GLAXO','KPITTECH','ACC','GLENMARK','MOTILALOFS','AWL','COFORGE','UPL','COCHINSHIP','FEDERALBNK','FORTIS','SONACOMS','JUBLFOOD','LTF','HONAUT','BIOCON','TATATECH','BDL','PAYTM','LLOYDSME','GUJGASLTD','NAM_INDIA','ESCORTS','MAHABANK','KEI','AIAENG','GODREJIND','M_MFIN','APARINDS','EXIDEIND','3MINDIA','APLAPOLLO','GODFRYPHLP','MFSL','DEEPAKNTR','360ONE','AJANTPHARM','BLUESTARCO','NIACL','IGL','NLCINDIA','LICHSGFIN','IRB','IPCALAB','CHOLAHLDNG','SYNGENE','JKCEMENT','STARHEALTH','KAYNES','ENDURANCE','DALBHARAT','BANDHANBNK','CRISIL','TATAINVEST','NATIONALUM','ABFRL','METROBRAND','MRPL','BRIGADE','HSCL','EMAMILTD','SUNTV','APOLLOTYRE','INOXWIND','NBCC','DELHIVERY','CDSL','HINDCOPPER','MSUMI','MANYAVAR','ZFCVINDIA','POONAWALLA','CENTURYTEX','GLAND','PPLPHARMA','RADICO','SUMICHEM','MEDANTA','MCX','KPRMILL','GILLETTE','SUVENPHAR','BAYERCROP','SUNDRMFAST','JBCHEPHARM','CROMPTON','CARBORUNIV','TIMKEN','ISEC','PNBHOUSING','NATCOPHARM','ITI','AEGISLOG','LALPATHLAB','SKFINDIA','GRINDWELL','KEC','LAURUSLABS','NH','RATNAMANI','WHIRLPOOL','TATACHEM','CESC','ARE_M','POLYMED','CASTROLIND','SHYAMMETL','KANSAINER','PEL','DEVYANI','NUVAMA','EIHOTEL','TRITURBINE','ANGELONE','KAJARIACER','APLLTD','JBMA','ELGIEQUIP','BIKAJI','JINDALSAW','CONCORDBIO','CYIENT','HFCL','JWL','ATUL','GSPL','FIVESTAR','IIFL','KPIL','CAMS','CIEINDIA','KIMS','AFFLE','FINCABLES','IRCON','TEJASNET','FSL','ASTERDM','CHAMBLFERT','SIGNATURE','JAIBALAJI','BLUEDART','AARTIIND','IEX','PCBL','VGUARD','SOBHA','RAMCOCEM','JYOTHYLAB','CREDITACC','GRSE','CENTURYPLY','NCC','CELLO','JUBLPHARMA','ERIS','RRKABEL','BBTC','CHALET','FINPIPE','MGL','RKFORGE','TRIDENT','SWANENERGY','BATAINDIA','SCHNEIDER','SONATSOFTW','KFINTECH','INDIAMART','WELCORP','MANAPPURAM','GESHIP','IDFC','BSOFT','CGCL','WELSPUNLIV','TTML','HBLPOWER','TITAGARH','DCMSHRIRAM','DOMS','KARURVYSYA','ZENSARTECH','APTUS','ASTRAZEN','BLS','CLEAN','SWSOLAR','UTIAMC','FINEORG','PVRINOX','SANOFI','ASAHIINDIA','RITES','ANANDRATHI','ACE','NAVINFLUOR','BEML','GLS','KSB','HONASA','CRAFTSMAN','NSLNISP','AMBER','CAPLIPOINT','REDINGTON','RAILTEL','DATAPATTNS','EIDPARRY','UJJIVANSFB','AAVAS','VTL','ELECON','OLECTRA','MMTC','INTELLECT','PRAJIND','GRANULES','NUVOCO','WESTLIFE','RAINBOW','CHENNPETRO','AETHER','ECLERX','MINDACORP','DEEPAKFERT','RBLBANK','ALOKINDS','ZEEL','TANLA','QUESS','CUB','SAFARI','GPIL','JUBLINGREA','RAYMOND','ALKYLAMINE','RHIM','HAPPSTMNDS','JMFINANCIL','SAMMAANCAP','CEATLTD','GMDCLTD','ENGINERSIN','CANFINHOME','J_KBANK','BALRAMCHIN','PNCINFRA','GRAPHITE','INDIACEM','HAPPYFORGE','MAPMYINDIA','RTNINDIA','HOMEFIRST','METROPOLIS','SAPPHIRE','CERA','GPPL','USHAMART','RCF','TRIVENI','ROUTE','CAMPUS','LEMONTREE','PRSMJOHNSN','JUSTDIAL','BIRLACORPN','RENUKA','CCL','SAREGAMA','LATENTVIEW','GNFC','FDC','NETWORK18','EQUITASBNK','SBFC','AVANTIFEED','VIJAYA','KNRCON','JKLAKSHMI','GSFC','TVSSCS','HEG','MAHSEAMLES','ACI','VARROC','RAJESHEXPO','CHEMPLASTS','SUNTECK','ANURAS','MHRIL','MASTEK','MAHLIFE','LXCHEM','TV18BRDCST','MEDPLUS','EPL','SYRMA','TMB','JKPAPER','BALAMINES','EASEMYTRIP','SPARC','KRBL','VIPIND','INDIGOPNTS','ALLCARGO','BORORENEW','GMMPFAUDLR','STLTECH','PRINCEPIPE','GAEL','CSBBANK','MTARTECH','RBA','VAIBHAVGBL']
}

ticker_option = st.radio("Step-1: Select script type", list(stock_options.keys()), horizontal=True)

# Text input for user tickers
if ticker_option == "Custom Symbol":
    user_tickers = st.text_input("You can edit these symbols if needed (comma-separated):", "SBIN, TCS, ITC")
else:
    # Populate the text input with predefined stock symbols and disable editing
    default_tickers = ", ".join(stock_options[ticker_option])
    user_tickers = st.text_input(f"Predifined stocks for {ticker_option}:", default_tickers, disabled=True)

# Create tickers list from user input
tickers = [ticker.strip() for ticker in user_tickers.split(',')] if user_tickers else []

# Proceed with the rest of your code...
interval_options = {
    '1 Minute': Interval.in_1_minute,
    '3 Minutes': Interval.in_3_minute,
    '5 Minutes': Interval.in_5_minute,
    '10 Minutes': Interval.in_5_minute,
    '15 Minutes': Interval.in_15_minute,
    '30 Minutes': Interval.in_30_minute,
    '45 Minutes': Interval.in_45_minute,
    '1 Hour': Interval.in_1_hour,
    '75 Minutes': Interval.in_15_minute,
    '2 Hours': Interval.in_2_hour,
    '125 Minutes': Interval.in_5_minute,
    '3 Hours': Interval.in_3_hour,
    '4 Hours': Interval.in_4_hour,
    '1 Day': Interval.in_daily,
    '1 Week': Interval.in_weekly,
    '1 Month': Interval.in_monthly
}

col1, col2 = st.columns(2)
with col1:
    max_base_candles = st.number_input('Select max_base_candles', min_value=1, max_value=6, value=1, step=1)
with col2:
    user_input_zone_distance = st.number_input("Current price to zone entry price distance in %", min_value=1, value=10)

# Time Interval Selection Popover
col1, col2 = st.columns(2)
with col1:
    with st.popover("Select Time Intervals", use_container_width=True):
        st.markdown("Choose the time intervals you want to scan:")
        select_all_intervals = st.checkbox("Select All", key="select_all_intervals")

        selected_intervals = []
        for interval_name in interval_options.keys():
            is_selected = st.checkbox(interval_name, value=select_all_intervals)
            if is_selected:
                selected_intervals.append(interval_name)

        if select_all_intervals:
            selected_intervals = list(interval_options.keys())

        st.session_state["selected_intervals"] = selected_intervals

    intervals = [interval_options[interval] for interval in selected_intervals]

    htf_intervals = []
    for selected_interval in selected_intervals:
        if selected_interval == '1 Minute':
            htf_intervals.append(Interval.in_15_minute)
        elif selected_interval in ['3 Minutes', '5 Minutes']:
            htf_intervals.append(Interval.in_1_hour)
        elif selected_interval in ['10 Minutes', '15 Minutes']:
            htf_intervals.append(Interval.in_daily)
        elif selected_interval in ['1 Hour', '75 Minutes', '2 Hours', '125 Minutes']:
            htf_intervals.append(Interval.in_weekly)
        elif selected_interval in ['3 Hours', '4 Hours', '1 Day', '1 Week', '1 Month']:
            htf_intervals.append(Interval.in_monthly)

with col2:
    # Zone Status Selection Popover
    with st.popover("Select Zone Statuses", use_container_width=True):
        st.markdown("Choose the zone statuses you want to scan:")
        select_all_statuses = st.checkbox("Select All", key="select_all_statuses")
        fresh_zone_allowed = st.checkbox("Fresh Zone", value=True)
        target_zone_allowed = st.checkbox("Target Zone", value=select_all_statuses)
        stoploss_zone_allowed = st.checkbox("Stoploss Zone", value=select_all_statuses)

        if select_all_statuses:
            fresh_zone_allowed = True
            target_zone_allowed = True
            stoploss_zone_allowed = True

        st.session_state["fresh_zone_allowed"] = fresh_zone_allowed
        st.session_state["target_zone_allowed"] = target_zone_allowed
        st.session_state["stoploss_zone_allowed"] = stoploss_zone_allowed

col1, col2 = st.columns(2)

with col1:
    # Zone Type Selection Popover
    with st.popover("Select Zone Types", use_container_width=True):
        st.markdown("Choose the zone types you want to scan:")
        select_all_types = st.checkbox("Select All", value=True)
        scan_demand_zone_allowed = st.checkbox("Scan Demand", value=select_all_types)
        scan_supply_zone_allowed = st.checkbox("Scan Supply", value=select_all_types)

        if select_all_types:
            scan_demand_zone_allowed = True
            scan_supply_zone_allowed = True

        st.session_state["scan_demand_zone_allowed"] = scan_demand_zone_allowed
        st.session_state["scan_supply_zone_allowed"] = scan_supply_zone_allowed


with col2:
    # Validation Types Selection Popover
    with st.popover("Select Validation Types", use_container_width=True):
        st.markdown("Choose the validation types you want to scan:")
        select_all_validation_types = st.checkbox("Select All", key="select_all_validation_types")
        candle_behinde_legin_check_allowed = st.checkbox("Check Candle Behind Legin Covered", value=select_all_validation_types)
        whitearea_check_allowed = st.checkbox("Check White Area in Zone", value=select_all_validation_types)
        legout_formation_check_allowed = st.checkbox("Check Legout formation ", value=select_all_validation_types)
        wick_in_legin_allowed = st.checkbox("Check wick in legin ", value=select_all_validation_types)
        time_validation_allowed = st.checkbox("Include time validation ", value=select_all_validation_types)
        legin_tr_atr_check_allowed = st.checkbox("Include TR > ATR ", value=select_all_validation_types)
        one_legout_count_allowed = st.checkbox("Include 1 legout only ", value=select_all_validation_types)
        three_legout_count_allowed = st.checkbox("Include 3 legout only ", value=select_all_validation_types)
        legout_covered_check_allowed = st.checkbox("Include legout covered check ", value=select_all_validation_types)

        if select_all_validation_types:
            candle_behinde_legin_check_allowed = True
            whitearea_check_allowed = True
            legout_formation_check_allowed = True
            wick_in_legin_allowed = True
            time_validation_allowed = True
            legin_tr_atr_check_allowed = True
            one_legout_count_allowed = True
            three_legout_count_allowed = True
            legout_covered_check_allowed = True
            
        st.session_state["candle_behinde_legin_check_allowed"] = candle_behinde_legin_check_allowed
        st.session_state["whitearea_check_allowed"] = whitearea_check_allowed
        st.session_state["legout_formation_check_allowed"] = legout_formation_check_allowed
        st.session_state["wick_in_legin_allowed"] = wick_in_legin_allowed
        st.session_state["time_validation_allowed"] = time_validation_allowed
        st.session_state["legin_tr_atr_check_allowed"] = legin_tr_atr_check_allowed
        st.session_state["one_legout_count_allowed"] = one_legout_count_allowed
        st.session_state["three_legout_count_allowed"] = three_legout_count_allowed        
        st.session_state["legout_covered_check_allowed"] = legout_covered_check_allowed        


reward_mapping = {
    '1 Minutes': 3,
    '3 Minutes': 3,
    '5 Minutes': 3,
    '1 Day': 10,
    '1 Week': 10,
    '1 Month': 10
}
 
nse = mcal.get_calendar('NSE')

# Get today's date
end_date = datetime.now()

days_back = st.slider('Select Scan period days', min_value=1, max_value=5000, value=365)

# Calculate the start date based on the selected number of days
start_date = end_date - timedelta(days=days_back-1)

# Get the trading days in the specified range
trading_days = nse.schedule(start_date=start_date, end_date=end_date)

# Define candles for each time frame
candles_count = {
        '1 Minute': 375,
        '3 Minutes': 125,
        '5 Minutes': 75,
        '10 Minutes': 38,
        '15 Minutes': 25,
        '30 Minutes': 13,
        '45 Minutes': 8,  # Approximation
        '1 Hour': 7,
        '75 Minutes': 5,        
        '2 Hours': 4,
        '125 Minutes': 3,        
        '3 Hours': 2,
        '4 Hours': 1,
        '1 Day': 1,
        '1 Week': 5,
        '1 Month': 20,
    }
find_patterns_button = st.button(label='🔍 Scan Now')

all_patterns = []

if find_patterns_button:
    patterns_found_button_clicked = True
    progress_bar = st.progress(0)
    progress_text = st.empty()
    progress_percent = 0
    start_time = time.time()
    patterns_found = []
    any_patterns_found = False  # Initialize the flag

    for i, ticker in enumerate(tickers):
        progress_percent = (i + 1) / len(tickers)
        progress_bar.progress(progress_percent)
        progress_text.text(f"🔍 Scanning Zone for {ticker}: {i + 1} of {len(tickers)} Stocks Analyzed")

        for idx, interval in enumerate(intervals):
            try:
                interval_key = selected_intervals[idx]
                reward_value = reward_mapping.get(interval_key, 5)                
                # Get the number of candles for the selected interval
                candles_in_selected_time_frame = candles_count[selected_intervals[idx]]
                
                # Get the count of trading days
                trading_days_count = len(trading_days)

                # Calculate the total number of candles
                n_bars = trading_days_count * candles_in_selected_time_frame
                exchange = 'NSE'
                htf_interval = htf_intervals[idx] if idx < len(htf_intervals) else None
                multiple_of_n_bars = 5000
                # Fetch stock data based on the selected intervals
                if selected_intervals[idx] in ['10 Minutes', '75 Minutes', '125 Minutes']:
                    stock_data = fetch_stock_data_and_resample(ticker, exchange, multiple_of_n_bars, htf_interval, interval, interval_key)
                else:
                    stock_data = fetch_stock_data(ticker, exchange, n_bars, htf_interval, interval)
                
                # Ensure stock_data is valid before proceeding
                if stock_data is None:
                    #st.warning(f"No data returned for {ticker} with interval {interval}. Skipping...")
                    continue

                # Calculate ATR and clean up the DataFrame
                stock_data = calculate_atr(stock_data)
                columns_to_remove = ['symbol', 'tr1', 'tr2', 'tr3', 'previous_close']
                stock_data = stock_data.drop(columns=columns_to_remove, errors='ignore')
                #st.write(candle_behinde_legin_check_allowed , whitearea_check_allowed)
                patterns = find_patterns(ticker, stock_data, interval_key, max_base_candles, scan_demand_zone_allowed, scan_supply_zone_allowed,reward_value,fresh_zone_allowed,target_zone_allowed,stoploss_zone_allowed,candle_behinde_legin_check_allowed , whitearea_check_allowed, legout_formation_check_allowed,wick_in_legin_allowed,time_validation_allowed,legin_tr_atr_check_allowed,one_legout_count_allowed,three_legout_count_allowed,legout_covered_check_allowed, htf_interval,user_input_zone_distance)

                if patterns:
                    any_patterns_found = True  # Set the flag if patterns are found
                    patterns_found.extend(patterns)  # Collect found patterns

            except Exception as e:
                st.error(f"Error processing {ticker} with interval {interval}: {e}")
                continue  # Handle exceptions as needed

    progress_bar.progress(1.0)

    if patterns_found:
        my_patterns_df = pd.DataFrame(patterns_found).drop_duplicates(subset=['Entry_Price', 'Stop_loss'], keep=False)
        patterns_df = my_patterns_df.sort_values(by='Zone_Distance', ascending=True).reset_index(drop=True)

        # Calculate and display elapsed time
        end_time = time.time()
        elapsed_time = end_time - start_time
        st.success(f"🔍 Scanning completed in {elapsed_time:.2f} seconds for {days_back} calendar days, which have {trading_days_count} trading days.")

        patterns_df['Pulse_and_trend'] = patterns_df['Pulse_details'] + patterns_df['Trend']


        
        # Displaying data and charts
        tab1, tab2 = st.tabs(["📁 Data", "📈 Chart"])
        with tab1:
            st.markdown("**Table View**")
            st.dataframe(patterns_df.drop(columns=['OHLC_Data', 'Close_price', 'Exit_index', 'Entry_index', 'Pulse_and_trend'], errors='ignore'))


        with tab2:
            st.markdown("**Chart View**")

            if not patterns_df.empty:
                for index, row in patterns_df.iterrows():
                    ticker_name = row['Symbol']
                    ohlc_data = row['OHLC_Data']
                    legin_date = row['legin_date']  # Ensure these fields exist in your DataFrame
                    legout_date = row['legout_date']
                    base_count = row['base_count']
                    Entry_Price = row['Entry_Price']
                    Stop_loss = row['Stop_loss']
                    Minimum_target = round(row['Target'],2)
                    ltf_time_frame = row['Time_frame']  # Make sure 'interval' is defined
                    pattern_name = row['Zone_Type']  
                    pulse_details   = row['Pulse_details']
                    trend = row['Trend']
                    Zone_status = row['Zone_status']
                    eod_close = row['Close_price']

                    # Filter out non-trading dates
                    ohlc_data = ohlc_data.dropna(subset=['Open', 'High', 'Low', 'Close'])

                    hover_text = [
                        f"Open: {row['Open']}<br>" +
                        f"High: {row['High']}<br>" +
                        f"Low: {row['Low']}<br>" +
                        f"Close: {row['Close']}<br>" +
                        f"TR: {row['TR']}<br>" +
                        f"ATR: {row['ATR']}<br>" +
                        f"Body: {row['Candle_Body']}<br>" +
                        f"Range: {row['Candle_Range']}"
                        for _, row in ohlc_data.iterrows()
                    ]

                    # Create a candlestick chart
                    fig = go.Figure(data=[go.Candlestick(
                        x=ohlc_data.index,
                        open=ohlc_data['Open'],
                        high=ohlc_data['High'],
                        low=ohlc_data['Low'],
                        close=ohlc_data['Close'],
                        name=ticker_name,
                        increasing_line_color='#26a69a',  # Set increasing line color
                        decreasing_line_color='#ef5350',  # Set decreasing line color
                        increasing_fillcolor='#26a69a',   # Set increasing fill color
                        decreasing_fillcolor='#ef5350',   # Set decreasing fill color
                        line_width=1,  # Set line thickness
                        hovertext=hover_text,  # Set custom hover text
                        hoverinfo='text'  # Show only custom hover text
                    )])
                    try:
                        legout_candle_index = ohlc_data.index.get_loc(legout_date)
                    except KeyError:
                        legout_candle_index = None  # Handle the case where legout_date is not found

                    # Determine shape_start based on legin_date
                    try:
                        shape_start = ohlc_data.index[ohlc_data.index.get_loc(legin_date)]
                    except KeyError:
                        if legout_candle_index is not None:
                            shape_start = legout_candle_index - base_count
                        else:
                            shape_start = None  # Handle the case where both dates are not found

                    shape_end = ohlc_data.index[-1]

                    # Add the rectangle shape based on pattern type
                    if pattern_name in ['DZ(RBR)', 'DZ(DBR)']:
                        fill_color = "green"
                    elif pattern_name in ['SZ(DBD)', 'SZ(RBD)']:
                        fill_color = "red"

                    # Add the rectangle shape if shape_start is valid
                    if shape_start is not None:
                        fig.add_shape(
                            type="rect",
                            xref="x",
                            yref="y",
                            x0=shape_start,
                            y0=Stop_loss,
                            x1=shape_end,
                            y1=Entry_Price,
                            fillcolor=fill_color,
                            opacity=0.2,
                            layer="below",
                            line=dict(width=0),
                        )                    
                    # Add a horizontal line for Minimum_target
                    fig.add_shape(
                        type="line",
                        x0=ohlc_data.index[0],  # Start at the first index of the OHLC data
                        y0=Minimum_target,
                        x1=shape_end,
                        y1=Minimum_target,
                        line=dict(color="lightgreen", width=2, dash="dash"),  # Set color to light green
                    )
                    # Add Target text label
                    fig.add_annotation(
                        x=shape_end,  # Position the label at shape_end
                        y=Minimum_target,  # Align with the Minimum_target line
                        text=f'Target: ₹ {Minimum_target}',  # Text for the label
                        showarrow=True,
                        arrowhead=2,
                        ax=-10,  # Adjust x position
                        ay=-10,  # Adjust y position
                        font=dict(size=10, color='black'),
                        bgcolor='white',
                        bordercolor='lightgreen',
                        borderwidth=1,
                        borderpad=4
                    )                    
                    if pattern_name in ['SZ(RBD)', 'SZ(DBD)']:                    
                       fixed_distance = 0.5  # Adjust this value as needed
                       # Add text annotations for Entry_Price and Stop_loss
                       fig.add_annotation(
                           x=shape_end,
                           y=Stop_loss + fixed_distance,
                           text=f'Stop Loss: ₹ {Stop_loss}',
                           showarrow=True,
                           arrowhead=2,
                           ax=10,
                           ay=-10,
                           font=dict(size=10, color='black'),
                           bgcolor='white',
                           bordercolor='red',  # Added border color for better contrast
                           borderwidth=1,  # Added border width
                           borderpad=4                        
                       )

                       fig.add_annotation(
                           x=shape_end,
                           y=Entry_Price,
                           text=f'Entry: ₹ {Entry_Price}',
                           showarrow=True,
                           arrowhead=2,
                           ax=10,
                           ay=10,
                           font=dict(size=10, color='black'),
                           bgcolor='white',
                           bordercolor='green',  # Added border color for better contrast
                           borderwidth=1,  # Added border width
                           borderpad=4                        
                        
                       )
                    else:
                       fixed_distance = 0.5  # Adjust this value as needed
                       # Add text annotations for Entry_Price and Stop_loss
                       fig.add_annotation(
                           x=shape_end,
                           y=Entry_Price,
                           text=f'Entry: ₹ {Entry_Price}',
                           showarrow=True,
                           arrowhead=2,
                           ax=10,
                           ay=-10,
                           font=dict(size=10, color='black'),
                           bgcolor='white',
                           bordercolor='green',  # Added border color for better contrast
                           borderwidth=1,  # Added border width
                           borderpad=4                        
                       )

                       fig.add_annotation(
                           x=shape_end,
                           y=Stop_loss + fixed_distance,
                           text=f'Stop Loss: ₹ {Stop_loss}',
                           showarrow=True,
                           arrowhead=2,
                           ax=10,
                           ay=10,
                           font=dict(size=10, color='black'),
                           bgcolor='white',
                           bordercolor='red',  # Added border color for better contrast
                           borderwidth=1,  # Added border width
                           borderpad=4                        
                        
                       )    
                    
                    # Update layout to remove datetime from x-axis and enhance the chart
                    fig.update_layout(
                        title = (
                            f'Chart: {ticker_name} ⎜ '
                            f'{ltf_time_frame} ⎜'                            
                            f'<span>{pattern_name} ⎜</span> '
                            f'<span>{pulse_details} ⎜</span> '
                            f'<span>Trend:{trend} ⎜</span> '
                            f'<span>Zone_status:{Zone_status}</span>'
                        ),
                        title_x=0.5,  # Center the title
                        title_xanchor='center',  # Anchor the title to the center
                        yaxis_title='Price',
                        xaxis_rangeslider_visible=False,  # Hide the range slider
                        xaxis_showgrid=False,  # Disable grid for cleaner look
                        margin=dict(l=0, r=0, t=100, b=40),  # Adjust margins
                        height=600,  # Set height for better presentation
                        width=800,   # Set width for better presentation
                        xaxis=dict(
                            type='category',  # Set x-axis to category to avoid gaps
                            tickvals=[],  # Clear tick values to stop displaying dates
                            ticktext=[],  # Clear tick text to stop displaying dates
                            fixedrange=False,  # Disable zooming on x-axis
                            range=[0, 24],
                            autorange=True
                        ),
                        yaxis=dict(
                            autorange=True,
                            fixedrange=True  # Disable zooming on y-axis
                        ),
                        dragmode='pan'  # Enable panning mode                  
                    )

                    # Add styled header annotation with increased y position
                    header_text = (
                        f"<span style='padding-right: 20px;'><b>👉 Legin Date:</b> {legin_date}</span>"
                        f"<span style='padding-right: 20px;'><b>👉 Base Count:</b> {base_count}</span>"
                        f"<span style='padding-right: 20px;'><b>👉 Legout Date:</b> {legout_date}</span>"                 
                       
                    )

                    fig.add_annotation(
                        x=0.5,
                        y=1.1,  # Increased y position for more space
                        text=header_text,
                        showarrow=False,
                        align='center', 
                        xref='paper',
                        yref='paper',
                        font=dict(size=14, color='black'),
                        bgcolor='rgba(255, 255, 255, 0.8)',  # Light background for header
                        borderpad=4,
                        width=800,
                        height=50,
                        valign='middle'
                    )
                            
                    # Display the chart in Streamlit 
                    st.plotly_chart(fig)
                    if (index + 1) % 5 == 0:
                        time.sleep(5)  # Sleep for 5 seconds                    

    else:
        st.info("No patterns found for the selected tickers and intervals.")
            
    progress_bar.empty()
    progress_text.empty()   
