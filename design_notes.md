# Design notes
Some general notes regarding the design option for our trading platform.
## Inheritance vs Composition
While a composition design is generally preferable, due to us having a fixed and limited number of agent types it might be appropriate for us to use an interface to define the general behaviour of agents and provide specific implementations for each agent type.

Inheritance model:
Agent interface -> agent implementations (building, store, grid)
Agent interface -> Consumer/producer/storage abstract classes -> implementations?
Agent interface -> Seller/buyer abstract class/interface -> implementation?
Each agent implementation has production and consumption properties

Composition model:
Agent class /w type property, consumption and production.
Type needed, or just prod/cons?

## Separating buyer/seller agents
For the grid actor it could make sense to split the selling and buying operations between two independed agents, since the grid will always be buying and selling at some price.

For other actors however, there might be dependencies between buying and selling bids, and thus it might be necessary for a single agent to handle both cases for each actor.
