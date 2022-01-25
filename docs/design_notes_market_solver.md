#  <span style="color:SkyBlue">Design notes</span>
Notes on how to design and implement a basic market solver for our trading platform.

##  <span style="color:SkyBlue">Basic Concept</span>
The basic concept is that a market solver takes all bids, and resolves them in such a way that bidding agents recieve the energy that they are bidding for within the confines of their boundaries.

For this simplified version with only local production, local consumption and an external grid, we can simply assume that the local consumers will buy as much as possible from local producers as long as the price is lower than buying from the external grid. Likewise, local producers will sell as much as possible to local consumers as long as the price is higher than selling to the external grid.

##  <span style="color:SkyBlue">Program flow</span>
Which entity should be "driving" the trades? Is the market solver active, and requesting bids from each agent for each trading step, or is it passive, awaiting bids from the agents? E.g. who initializes trade?

From a programming standpoint, it seems simpler for the market solver to be running the base loop. All bidding agents are registered with the market solver, and at the start of each trading period the market solver asks each agent to make a bid. Once all bids have been received, it can start finding a solution.

Alternatively, should the core loop be handled by a static main function separate from the instantiated objects, which requests all bids and passes them to the market solver?