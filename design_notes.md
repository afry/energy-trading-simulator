#  <span style="color:SkyBlue">Design notes</span>.
Some general notes regarding the design option for our trading platform.

Initially, they were intended to include agents for buildings, store and grid. However, since we decided to focus on electricity instead of heat, it seems that replacing the store with a PV park for the role of producer makes sense.

##  <span style="color:SkyBlue">Inheritance vs Composition</span>
While a composition design is generally preferable, due to us having a fixed and limited number of agent types it might be appropriate for us to use an interface to define the general behaviour of agents and provide specific implementations for each agent type.

Inheritance model:
Agent interface -> agent implementations (building, store, grid)
Agent interface -> Consumer/producer/storage abstract classes -> implementations?
Agent interface -> Seller/buyer abstract class/interface -> implementation?
Each agent implementation has production and consumption properties

Composition model:
Agent class /w type property, consumption and production.
Type needed, or just prod/cons?

##  <span style="color:SkyBlue">Separating buyer/seller agents</span>
For the grid actor it could make sense to split the selling and buying operations between two independed agents, since the grid will always be buying and selling at some price.

For other actors however, there might be dependencies between buying and selling bids, and thus it might be necessary for a single agent to handle both cases for each actor.


##  <span style="color:SkyBlue">Agent core concept</span>
At it's core, an agent is an entity that takes a projected surplus or deficit of some type of energy, and makes a bid towards the market to reduce that surplus or deficit. How to we represent this as an object in a program?

###  <span style="color:SkyBlue">Deficit/surplus</span>
Deficit and surplus could either be viewed as positive/negative of the same value, "Resource amount", or as two separate values, "surplus" and "deficit".

In the first case, a surplus would be indicated by a positive amount of the resource, while a deficit would be indicated by a negative amount. A bit would then strive to move towards some value, likly a smaller net positive.

How would bid dependencies work in this case? E.g. "I want to buy in case A, but sell in case B"? Is this a feasible situation when trading only one resource and excluding storage?

In the second case, it would likely be easier to support dependencies, but is that necessary? Are there other structural reasons one might be preferable to the other?

###  <span style="color:SkyBlue">Price</span>
Price is paid by the entity recieving a resource to the entity providing it. Meaning the entity with a surplus (positive resource) gains money while an entity with a deficit (negative resource) loses it. We can also assume that payments are 1:1 for simplicity's sake. So, in case A payment can be calculated as resource amount *r* multiplied by price *p* for both parties. This results in a negative "payment" for the buyer and a positive "payment" for the seller, which can be directly added to their "bank"

In case B, the same can be achieved by multiplying the deficit "payment" with -1.

##  <span style="color:SkyBlue">Agent functions</span>
The agent would have two primary functions: calculate projected deficit/surplus for the trading horizon, and making a bid towards the market

###  <span style="color:SkyBlue">Calculate deficit/surplus</span>
This would be based on the output from som manner of digital twin, either in the form of a physics-based simulation or some simpler data-driven simulation. Which doesn't matter for the purposes of this platform, as long as a prognosis for energy needs or production are provided

###  <span style="color:SkyBlue">Make a bid</span>
Once energy requirements are know, the agent can make a bid toward the market. A bit should consist of an energy amount (kWh) and a price (SEK/kWh).

Do we support multi-party bid resolution? Say, if a building has a higher power requirement that any single provider can meet, can it be filled by multiple providers? And vice versa, can a large producer supply multiple consumers with a single bid, or should these be split into multiple bids?

How do we implement bid flexibility? 

### <span style="color:SkyBlue">Function flow </span>
Should agents keep some sort of state based on the outcome of the prognosis, or should the bidding function be called directly from the prognosis at each time interval?

##  <span style="color:SkyBlue">Grid agents</span>
Grid agents seem to be fundamentally different it two key ways
1. They don't have a fixed amount of energy they can offer/accept, but rather act as an energy reservoir.
2. As a result of this, they have no need to make prognosis for their production or absorbtion capacity.
