# -*- coding: utf-8 -*-
"""
Created on Sat Oct 12 14:02:48 2024

@author: konst
"""
#Importing needed packages
import gurobipy as gp
import pandas as pd
from gurobipy import GRB

##################################Data Import and cleaning#################################################


# Load the raw data from excel
nordpool_price = pd.read_csv('Data/NordPool.csv', delimiter=';')
energinet_price = pd.read_csv('Data/Energinet Balance price.csv', delimiter=';')
production_forecast = pd.read_csv('Data/Wind Production Forecast.csv')

# Filter the Energinet data to only include zone DK2
filtered_energinet_price = energinet_price[energinet_price['PriceArea | PriceArea | 804696'] == 'DK2']
energinet_price = filtered_energinet_price

# Convert the 'ts' column to datetime format for each dataset
nordpool_price['ts'] = pd.to_datetime(nordpool_price['ts'], dayfirst=True)
energinet_price['ts'] = pd.to_datetime(energinet_price['ts'], dayfirst=True)

# Set 'ts' as the index for each DataFrame
nordpool_price.set_index('ts', inplace=True)
energinet_price.set_index('ts', inplace=True)

#Filter out relevant columns for balancing prices list
columns_to_keep = ['BalancingPowerPriceUpEUR | BalancingPowerPriceUpEUR | 804718', 'BalancingPowerPriceDownEUR | BalancingPowerPriceDownEUR | 804720'] 
energinet_price = energinet_price[columns_to_keep]


#Create an average day for day ahead and balancing market
nordpool_price['hour'] = nordpool_price.index.hour
average_nordpool = nordpool_price.groupby('hour').mean()

energinet_price['hour'] = energinet_price.index.hour
average_energienet = energinet_price.groupby('hour').mean()




################Setting Input parameters###########################################


Number_of_Hours = 24
NamePlate_Capacity = 100


##############Defining the optimization model########################################


#Defining the gurobi model

model = gp.Model("Wind Power Optimization")

#Defining the variables

#Variable for the energy that is bid in the day ahead market
DA_Bid = model.addVars(Number_of_Hours, vtype=GRB.CONTINUOUS, name="DA_Bid")

#Variable if the production was actually higher than what was bid on the day ahead market, this number will be sold on the balancing market
Balance_Up = model.addVars(Number_of_Hours, vtype=GRB.CONTINUOUS, name="Balance_Up")

#Variable if the production was actually lower than what was bid on the day ahead market, this deficit will be purchased on the balancing market
Balance_Down = model.addVars(Number_of_Hours, vtype=GRB.CONTINUOUS, name="Balance_Down")

#Variable that describes the delta between day ahead bid and actual production
Delta = model.addVars(Number_of_Hours, vtype=GRB.CONTINUOUS,lb=-GRB.INFINITY, name="Delta")

#Defining objective function
objective = (
    gp.quicksum(average_nordpool.loc[h, 'Nordpool Elspot Prices - hourly price DK-DK2 EUR/MWh | 9F7J/00/00/Nordpool/DK2/hourly_spot_eur | 3038'] * DA_Bid[h] for h in range(Number_of_Hours))
    + gp.quicksum(average_energienet.loc[h, 'BalancingPowerPriceDownEUR | BalancingPowerPriceDownEUR | 804720'] * Balance_Up[h] for h in range(Number_of_Hours))
    - gp.quicksum(average_energienet.loc[h, 'BalancingPowerPriceUpEUR | BalancingPowerPriceUpEUR | 804718'] * Balance_Down[h] for h in range(Number_of_Hours))
)
model.setObjective(objective, GRB.MAXIMIZE)


for t in range(Number_of_Hours):
    #Adding Constraint that defines delta as the difference between the day ahead bid and the actual power production. Delta is positive for overproduction, negative for underproduction
    model.addConstr(Delta[t] == production_forecast.loc[t,'Wind Production [MW]'] - DA_Bid[t], name=f"Defining Delta_{t}")
    #Adding constraint that defines the value for balance_up/down
    model.addConstr(Delta[t] == Balance_Up[t] - Balance_Down[t] , name=f"Defining Delta Up/Down_{t}")
    #Constraint that makes sure, that bid can´t be higher than the maximum capacity of the wind farm
    model.addConstr( DA_Bid[t] <= NamePlate_Capacity, name=f"Production Capacity_{t}")
    
model.optimize()


# # Check optimization result
if model.status == GRB.INFEASIBLE:
    print("Model is infeasible.")
elif model.status == GRB.UNBOUNDED:
    print("Model is unbounded.")
elif model.status == GRB.TIME_LIMIT:
    print("Time limit reached.")
elif model.status == GRB.OPTIMAL:
    print("Optimal solution found.")
    TotalRevenue = model.objVal
    print("Total Revenue: ", TotalRevenue)
    #Save results in data frame

    results = {
        'DA_Bid': [DA_Bid[t].X for t in range(Number_of_Hours)],
        'Balance_Up': [Balance_Up[t].X for t in range(Number_of_Hours)],
        'Balance_Down': [Balance_Down[t].X for t in range(Number_of_Hours)],
        'Delta': [Delta[t].X for t in range(Number_of_Hours)]
    }

    # Create a DataFrame from the dictionary
    results_df = pd.DataFrame(results)

    # Display the DataFrame
    print(results_df)














