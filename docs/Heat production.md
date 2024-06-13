Author: Bengt Dahlgren AB

## GROCERY STORE / SHOPPING CENTER

Here it is assumed that the grocery store corresponds to an ICA Maxi supermarket.
The refrigeration units in the store emit heat via the condenser.
Information about the available heat output is taken from the request documents for food refrigeration for an ICA store.

| Parameter                            | Value |
|--------------------------------------|-------|
| Total emitted heat output, daytime   | 80 kW |
| Total emitted heat output, nighttime | 60 kW |
| Operating hours, day                 | 14 h  |
| Temperature of emitted heat          | 45 °C |

**Assumptions:**

* Heat from the grocery store is available as outlined above for all weekdays (assumed opening hours 8 AM – 10 PM every day).
* Heat from the grocery store can be sold to the low-temperature network when it is operating at 45 °C.
* Thus, in the summer, in the winter it is assumed that the store uses the heat from the refrigeration units for its own heating needs.

## DATA / SERVER HALL
Here it is assumed that the agent is a small data center that is part of a block with office spaces. 
The definition of a small data center is taken from the RISE report "Energianvändning i datacenter och digitala system", Minde, T, 2023.

The assumption here is that the data center has varying cooling needs but operates continuously, day and night, throughout the year without seasonal variation.
The assumption is based on cooling being achieved through circulating air for the control of humidity and cleanliness.

| Parameter                                                    | Value   |
|:-------------------------------------------------------------|---------|
| Average power, emitted heat                                  | 150 kW  |
| Maximum power, emitted heat                                  | 200 kW  |
| Operating time                                               | 24 h    |
| Temperature, emitted heat                                    | 35 ℃    |
| Number                                                       | 2 units |
| COP (Coefficient of Performance) of heat pump, winter (65 ℃) | 4       |
| COP (Coefficient of Performance) of heat pump, summer (45 ℃) | 5       |

Assumptions:

* The heat from the data center is emitted at too low a temperature to be directly supplied to the local heating network. Therefore, a heat pump is used to raise the temperature and deliver it to the ring network.
* The COP (Coefficient of Performance) of the heat pump varies depending on the system temperature in the local heating system (45 or 65℃).
* The emitted heat power is assumed to vary depending on the data center load. Based on results from studies, the heat load seems to be relatively constant. If possible, the availability of heat should vary to reflect some variation, but if it becomes too complex, a constant heat supply with average power can be used.
* It is assumed here that two of the blocks with office spaces include a data center.

## SMALL INDUSTRY

Here, it is assumed that the agent is a small industry located near the area.
Based on the report “Spillvärme från industrier och lokaler”, Svensk Fjärrvärme, Rapport 2009:12,
it is assumed that this could be a food industry as these are often located near residential areas.

An assumption is that this could correspond to a bakery with ovens; this load is constant,
and if cooling of ovens is utilized as waste heat (not cooled by ventilation),
the load is assumed to be relatively independent of outdoor temperature.

The operation is assumed to run for 10 hours per day on weekdays and be closed on weekends.

| Parameter                 | Value    |
|:--------------------------|:---------|
| Power, emitted heat       | 300 kW   |
| Operating time, weekdays  | 10 h/day |
| Temperature, emitted heat | \>65 ℃   |

Assumptions:

* The heat from the bakery is assumed to be available at a sufficiently high temperature to always be sold to the local network (>65 ℃).