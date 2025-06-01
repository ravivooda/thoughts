When [Margaret Hamilton]() wrote Apollo Guidance, the mission critical software for Lunar Landing, it took her and the team 6+ years to build it. Her team consisted of 350 people at peak, comprising software engineers, mathematicians, System Analysts and more. She is also known for coining the term "Software Engineering" bringing many of current techniques like rigorous testing, error detection, task scheduling and management. Honestly she is so inspiring the more you learn about her.

If you look at the requirements of the system built, they can be summarized (somewhat naively) as following: 

1. Sensor Integration and Data Fusion: Read and sanitize inputs from gyrometers, accelerometers etc.
2. Actuator Control: Send commands to thrusters, throttlers. Integrate feedback loop.
3. Provide Fault Tolerance and Reliability: Gracefully handle hardware faults, restarts critical modules 
4. User Interface with Astronauts: Show System Health, metrics and controls to Astronauts. Allow manual overrides.
5. Task Prioritization: System should prioritize tasks with higher priority, for ex., controlling descent throttling. 

If you ask an MIT Research Labs in 2020 (pre-GPT era), they probably could build the system with 10 folks, but most importantly in a couple of years. (There is a whole rabbit hole of hardware limitations that we are not even accounting for).

If you ask the same question today, I think you could build it in 2 months with the support of LLM Models. 

In many ways, she and her team was generating a new paradigm of computing (aka software) manually. Every introduction of paradigm in the industry has made significant gains on overall developer velocity. A few examples come to mind: 

1. Object-Oriented Programming: Immensely helped reusability of code with inheritance, encapsulation etc.
2. Relational Databases: Made storing and fetching data on demand trivial. 
3. Cloud Infrastructure as Code: Instantaneous environments without massive investment in hardware, repeatable and scalable deployments.
4. Machine Learning Platforms: Identify patterns in logic, avoiding writing so many things manually.


But what made them THEM? What made them so powerful each time they cut velocity to develop in half in a specific domain?
We've often heard that responsibilities of modules/classes/teams/organizations should be clear, separate and minimal. But why is that? Is it because clean responsibilities give way to clean representation of logic? I fathom yes! 
When we build modules with minimal responsibilities and dependencies, it makes integration between the components trivial. (There is a tech debt aspect which we are not going into).

My thesis is if we adopt the same approach when utilizing LLM models for solving a complex problem (like bring up a social networking service globally), it would yeild more fruitful results than just throwing the LLM at the entire thing. 

In another words, instead of asking "help me build backend for social networking service", ask it solve each problem underneath step by step. (This is actually not that good of a list)

1. Help me choose a Cloud Provider (GCP vs Amazon)
2. Which Orchestration platform suits better? (Kubernetes vs ECS)
3. Design and implement user service (signup, login, sessions)
4. Build auth system (JWT, OAuth2 support, session tokens)
5. Implement feed service (CRUD posts, timeline queries)
6. Implement social graph service (follows, blocks, mutes)
7. Implement media service (upload, thumbnailing, video transcode)

and so on....

Now an LLM has a smaller problem to solve at each step, which mean the solutions generated have less chance of getting it wrong. This is kinda emulated in how teams and orgs are structured in a company too. Again it resonates, make everyone/everything minimally responsibile, clearly devided problems. 

I want to call this "Making Mazes Great Again"


