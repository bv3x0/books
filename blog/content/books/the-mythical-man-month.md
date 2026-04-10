---
title: "The Mythical Man-Month: Essays on Software Engineering, Anniversary Edition"
sortTitle: "Mythical Man-Month: Essays on Software Engineering, Anniversary Edition"
date: 2026-04-10
slug: "the-mythical-man-month"
draft: false
dateAdded: 2026-04-10
description: "Software projects fail primarily because of fundamental misunderstandings about how time, people, and complexity interact—adding more programmers to a late project makes it later, and no single technological development can produce an order-of-magnitude improvement in software productivity because the essential difficulties of software are inherent in its conceptual complexity, not in accidental implementation challenges."
bookKeywords: "software project management, conceptual integrity in system design, software productivity estimation, team organization and communication, essential vs. accidental complexity in software"
author: "Frederick P. Brooks, Jr."
shortAuthor: "Jr."
year: "1995"
tags: ["computers", "technology & engineering", "business & economics"]
collections: ["Terraform Industries"]
---



## The Tar Pit

Large-system programming is like a prehistoric tar pit—teams get mired because the gap between a simple working program and a fully documented, tested, generalizable 'programming systems product' multiplies effort ninefold, a cost that surprises almost everyone who underestimates what industrial software actually requires.

* <span id="the-mythical-man-month-essays-on-software-engineer-001"></span>**A simple program becomes a 'programming systems product' through two independent transformations—productizing (generalization, testing, documentation) and systemizing (interface conformance, resource budgets, integration testing)—each tripling cost, so the final product costs nine times the original program.**
    - A programming product must be written in generalized form, thoroughly tested with a bank of test cases, and fully documented so anyone can use, fix, or extend it—costing at least three times a debugged standalone program.
    - A programming system component must conform to precisely defined interfaces, stay within prescribed resource budgets, and be tested in all combinations with other components—also costing at least three times a standalone program.
* <span id="the-mythical-man-month-essays-on-software-engineer-002"></span>**Programming's unique joys stem from working in a purely tractable medium—the programmer, like a poet, builds from pure thought-stuff, and the constructs actually move and produce visible results, combining intellectual freedom with tangible effect.**
    - The five joys of programming: making things, making useful things for others, fashioning complex interlocking puzzle-like objects, always learning something new, and working in a medium so flexible and responsive to imagination.
    - "One types the correct incantation on a keyboard, and a display screen comes to life, showing things that never were nor could be." —Frederick P. Brooks, Jr.
* <span id="the-mythical-man-month-essays-on-software-engineer-003"></span>**Programming's inherent woes arise from the same tractability that makes it joyful—the medium's perfectibility demands perfect execution, creates dependence on others' imperfect programs, and produces work that is perpetually threatened by obsolescence before completion.**
    - Adjusting to the requirement for perfection—one wrong character and the magic fails—is the most difficult part of learning to program, since humans are unaccustomed to performing perfectly.
    - Debugging has linear convergence at best, so testing drags on and the last difficult bugs take more time to find than the first, contrary to optimistic expectations.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Space_orbit-with-rocket.png" alt="" role="presentation" loading="lazy"></div>

## The Mythical Man-Month

The man-month is a dangerous myth because men and months are interchangeable only for perfectly partitionable tasks with no communication requirements, while software construction's inherent sequential constraints and complex interdependencies mean that adding more people to a late project makes it later, not earlier.

* <span id="the-mythical-man-month-essays-on-software-engineer-004"></span>**Software projects fail most often due to insufficient calendar time, driven by optimism—programmers habitually assume all will go well, so schedules are built on the probability of zero delay in every sequential task, which becomes vanishingly small as tasks multiply.**
    - Dorothy Sayers's three stages of creative activity—idea, implementation, interaction—reveal why programmers are optimistic: the medium is so tractable that few implementation difficulties are expected, but the ideas themselves are faulty, so bugs appear anyway.
    - In a single task there is a finite probability that all will go well, but a large effort consists of many chained tasks; the probability that each will go well becomes vanishingly small.
* <span id="the-mythical-man-month-essays-on-software-engineer-005"></span>**The man-month unit is fundamentally deceptive because communication overhead scales as n(n-1)/2 with team size—adding workers to software tasks requiring coordination can increase rather than decrease total schedule time.**
    - Men and months are interchangeable only when a task can be partitioned with no communication among workers—true of reaping wheat, not of systems programming.
    - Training cannot be partitioned (adds linearly with workers), and intercommunication for pairwise coordination grows as n(n-1)/2, so three workers require three times as much intercommunication as two.
* <span id="the-mythical-man-month-essays-on-software-engineer-006"></span>**A realistic software schedule allocates 1/3 to planning, 1/6 to coding, and 1/2 to testing—yet most projects allocate far too little time to system test, ensuring that the worst news arrives last, when costs are highest.**
    - In conventionally scheduled projects, few allowed half the schedule for testing, but most did spend half the actual schedule on it—they simply weren't aware of the problem until the delivery date.
    - Delay at system test is especially costly because the project is fully staffed at maximum cost-per-day, and secondary costs from delayed software deliverables (supporting hardware shipments, operations) may dwarf development costs.
* <span id="the-mythical-man-month-essays-on-software-engineer-007"></span>**When a software project slips its first milestone, adding manpower triggers a regenerative disaster: new people require training by experienced members (consuming months of unplanned work), the task must be repartitioned, and system test time lengthens—producing a net result equal to or worse than no action.**
    - In a concrete example of a 12-man-month task two months behind schedule, adding two men means one experienced person trains them for a month, spending 3 man-months not in the original estimate, while repartitioning and extended system test eat further into progress.
    - The temptation to add yet more manpower at the third-month crisis point—when things look very black—leads to madness: a regenerative cycle ending in disaster.
    - "P. Fagg, an experienced hardware engineer, advised: 'Take no small slips'—allow enough time in any rescheduling to ensure work can be done carefully and rescheduling will not have to be done again." —P. Fagg


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Space_orbit-shuttle.png" alt="" role="presentation" loading="lazy"></div>

## The Surgical Team

Harlan Mills's 'surgical team' proposal resolves the dilemma between small-team conceptual integrity and large-team throughput by organizing around a single chief programmer whose work is amplified by specialized support roles, minimizing the number of minds that make design decisions while maximizing the hands available.

* <span id="the-mythical-man-month-essays-on-software-engineer-008"></span>**Productivity among professional programmers varies by an order of magnitude (10:1 in throughput, 5:1 in program speed and space), with no correlation to experience—making the composition of a team more important than its size.**
    - Sackman, Erikson, and Grant measured experienced programmers and found ratios between best and worst performance averaging 10:1 on productivity and 5:1 on program speed and space.
    - Brute-force large team approaches produce systems that are costly, slow, inefficient, and not conceptually integrated—OS/360, Exec 8, Multics, SAGE are examples.
* <span id="the-mythical-man-month-essays-on-software-engineer-009"></span>**Mills's surgical team organizes ten people around one 'chief programmer' who does all the designing and coding, supported by a copilot, administrator, editor, program clerk, toolsmith, tester, and language lawyer—reducing design authority to one or two minds while fielding ten workers.**
    - The copilot can do any part of the job but is less experienced; he serves as a design sounding board, writes no code he is responsible for, and represents the team in interface discussions—providing insurance against disaster to the surgeon.
    - The program clerk makes all computer runs visible to all team members and identifies all programs and data as team property, transforming programming from 'private art to public practice.'
    - The surgeon and copilot are each cognizant of all the design and all the code, unlike a conventional two-programmer team where partners divide the work and must negotiate all differences of judgment.
* <span id="the-mythical-man-month-essays-on-software-engineer-010"></span>**Scaling the surgical team to a 200-person project reduces coordination to 20 minds (the surgeons), solving the conceptual integrity problem at scale—but requires a separate system architect and sharp architecture/implementation separation.**
    - If 200 people are organized as surgical teams, the number of minds determining design is divided by seven, making it possible to coordinate only 20 minds rather than 200.
    - The entire system must have conceptual integrity requiring a system architect to design from the top down, strictly confining himself to architecture and leaving implementation to the teams.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Life_gears-mechanism.png" alt="" role="presentation" loading="lazy"></div>

## Aristocracy, Democracy, and System Design

Conceptual integrity—a system reflecting one coherent set of design ideas—is the most important property of a good software design, and achieving it requires separating architectural authority (what the system does for the user) from implementation (how it does it), with few architects controlling the former and many implementers free to be creative within it.

* <span id="the-mythical-man-month-essays-on-software-engineer-011"></span>**The ratio of function to conceptual complexity—not function alone or simplicity alone—is the ultimate test of system design, because ease of use requires that gaining function not cost more in learning than it saves in use.**
    - OS/360 was hailed for maximum function but not simplicity; the Time-Sharing System for the PDP-10 was hailed for simplicity but had far less function; both fail the ease-of-use test by reaching for only half the true goal.
    - Simplicity is not enough: Mooers's TRAC and Algol 68 minimize distinct elementary concepts but are not straightforward—the expression of desired things requires involuted, unexpected combinations, so one must learn idioms beyond the elements.
* <span id="the-mythical-man-month-essays-on-software-engineer-012"></span>**Architecture (the complete specification of the user interface—what happens) must be sharply separated from implementation (how it happens), as demonstrated by IBM's System/360 where one architecture was realized by nine different hardware models.**
    - "Blaauw: 'Where architecture tells what happens, implementation tells how it is made to happen'—illustrated by a clock whose architecture (face, hands, knob) is learned once and works for any clock regardless of the internal mechanism." —Blaauw
    - In System/360, a single implementation—the Model 30 data flow—served at different times for four different architectures: a System/360 computer, a multiplex channel, a selector channel, and a 1401 computer.
* <span id="the-mythical-man-month-essays-on-software-engineer-013"></span>**The 'aristocracy' of architects is justified because conceptual integrity requires controlled concepts, but implementation is equally creative work—the cost-performance ratio depends most on the implementer, not the architect, and external architecture actually enhances implementer creativity by eliminating architectural debates.**
    - "R. W. Conway's group at Cornell, building the PL/C compiler, decided to implement PL/I unchanged: 'The debates about language would have taken all our effort.'" —R. W. Conway
    - Bach's creative output was not squelched by producing a limited-form cantata each week; form is liberating—the constraints imposed by the System/360 Model 30's budget were entirely beneficial for the Model 75's architecture.
* <span id="the-mythical-man-month-essays-on-software-engineer-014"></span>**Brooks's OS/360 experience proved that allowing 150 implementers to write the external specifications—instead of a 10-man architecture team—produced work that was three months late anyway and of much lower quality, adding an estimated year to debugging time through lack of conceptual integrity.**
    - The architecture manager predicted the implementation team's spec would be three months late and lower quality; both proved correct, and the lack of conceptual integrity made the system far more costly to build and change.
    - Architecture, implementation, and realization can proceed in parallel—implementers can begin designing data flows, control sequences, and algorithms from rough approximations of specs while architecture is finalized.


<div class="chapter-glyph"><img src="/glyphs/Business & Economics/Earth_animal-livestock.png" alt="" role="presentation" loading="lazy"></div>

## The Second-System Effect

A designer's second system is the most dangerous one he ever builds because it absorbs all the ideas cautiously deferred from the first, producing over-designed, embellished results—and it often perfects techniques made obsolete by changed system assumptions, as OS/360 exemplifies repeatedly.

* <span id="the-mythical-man-month-essays-on-software-engineer-015"></span>**An architect's first system is spare and clean because he works with restraint born of uncertainty; his second system invites all the frills accumulated while building the first, leading to a dangerous tendency to over-design.**
    - IBM's 709 architecture (embodied in the 7090), an upgrade of the successful and clean 704, had an operation set so rich and profuse that only about half of it was regularly used.
    - "Strachey on the Stretch computer: 'It is immensely ingenious, immensely complicated, and extremely effective, but somehow at the same time crude, wasteful, and inelegant, and one feels that there must be a better way of doing things.'" —Strachey
* <span id="the-mythical-man-month-essays-on-software-engineer-016"></span>**OS/360 exemplifies the second-system effect doubly—both through functional embellishment (26 bytes of permanent code to handle December 31 on leap years) and through perfecting techniques made obsolete by changed assumptions.**
    - The OS/360 linkage editor was the finest static overlay facility ever built—also the last dinosaur, because OS/360's normal mode was multiprogramming with dynamic core allocation, making static overlays obsolete. It was slower than most compilers, defeating its own purpose of avoiding recompilation.
    - The TESTRAN debugging facility brought batch debugging to full bloom precisely as interactive computing and fast-compile/slow-execute compilers were making source-level debugging the preferred technique.
* <span id="the-mythical-man-month-essays-on-software-engineer-017"></span>**The architect avoids the second-system effect through conscious self-discipline—assigning explicit byte and microsecond budgets to each feature—and project managers avoid it by insisting on senior architects with at least two systems of prior experience.**
    - Assigning a priori values in bytes and microseconds to functions guides initial decisions and serves during implementation as a warning signal against embellishment.
    - The project manager should stay aware of the special temptations of the second system and ask the right questions to ensure philosophical concepts are fully reflected in detailed design decisions.


<div class="chapter-glyph"><img src="/glyphs/Business & Economics/Life_person-carrying.png" alt="" role="presentation" loading="lazy"></div>

## Passing the Word

Maintaining conceptual integrity across a thousand-person project requires a layered communication system—precise written manuals, formal definitions, direct code incorporation, regular conferences with clear decision authority, telephone logs of architectural interpretations, and an independent testing organization—all working together to ensure every implementer understands and accurately implements every architectural decision.

* <span id="the-mythical-man-month-essays-on-software-engineer-018"></span>**The architectural manual must describe everything the user sees with precision, refrain from prescribing implementation, and be written by only one or two people to ensure consistency of prose and the countless mini-decisions embedded in specification.**
    - The unity of System/360's Principles of Operation sprang from the fact that only two pens wrote it—Gerry Blaauw's and Andris Padegs'—ensuring that mini-decisions, such as how the Condition Code is set after each operation, were made consistently throughout.
    - Blaauw's appendix defining the limits of System/360 compatibility—prescribing what is achieved and enumerating areas where the architecture is intentionally silent—represents the level of precision to which manual writers must aspire.
* <span id="the-mythical-man-month-essays-on-software-engineer-019"></span>**Formal definitions offer precision and completeness but lack comprehensibility; prose definitions explain structure and rationale but lack rigor—so future specifications should include both, with one designated as the standard and the other explicitly derivative.**
    - An ancient adage warns: 'Never go to sea with two chronometers; take one or three.' If one has both prose and formal definitions, one must be the standard—Algol 68 uses formal as standard, PL/I uses prose as standard.
    - Using an implementation as a formal definition is tempting but dangerous: IBM's 1401 emulation for System/360 revealed 30 'curios'—side effects of supposedly invalid operations—that had come into widespread use and had to be treated as part of the definition.
* <span id="the-mythical-man-month-essays-on-software-engineer-020"></span>**Weekly architectural conferences with all teams, combined with annual 'supreme court' sessions before major freeze dates, provide both rapid decision-making and legitimate acceptance of contested decisions—with the chief architect holding unilateral decision power to avoid compromise and delay.**
    - The weekly conference's fruitfulness depends on the same bright, committed group meeting for months so no time is spent on background, with written proposals forcing decision and the chief architect's clear authority preventing compromise.
    - Annual supreme court sessions lasting two weeks—with architecture, programming, marketing, and implementation managers all present—resolved about 200 items per session; computerized text editing produced an updated manual at each participant's seat every morning.
* <span id="the-mythical-man-month-essays-on-software-engineer-021"></span>**Architects must maintain a telephone log of every implementer question and answer, published weekly to all parties, because every interpretation is an ex cathedra architectural pronouncement that must reach the entire team.**
    - The independent product-testing organization is the project manager's best friend and daily adversary—it serves as a surrogate customer specialized for finding flaws, and is a necessary link in the chain by which the design word is passed.


<div class="chapter-glyph"><img src="/glyphs/Business & Economics/Earth_figure-working.png" alt="" role="presentation" loading="lazy"></div>

## Why Did the Tower of Babel Fail?

The Tower of Babel failed not from lack of manpower, materials, time, or technology, but from lack of communication and the organizational breakdown that followed—and the same cause underlies most large software project failures today, requiring deliberate multi-channel communication strategies and carefully designed organization structures.

* <span id="the-mythical-man-month-essays-on-software-engineer-022"></span>**The Babel project had every prerequisite for success except communication and organization: teams drifted apart in their assumptions, coordination failed, work ground to a halt, and group jealousies caused dispersal—exactly the dynamic that drives schedule disaster, functional misfit, and system bugs in large software projects.**
    - Schedule disaster, functional misfits, and system bugs all arise because the left hand doesn't know what the right hand is doing—teams slowly change functions, sizes, speeds, and implicit assumptions without broadcasting those changes.
    - A concrete example: an implementer of a program-overlaying function reduces speed based on rarity statistics, while a neighbor simultaneously designs a supervisor that critically depends on that function's speed—a change that needs system-wide evaluation.
* <span id="the-mythical-man-month-essays-on-software-engineer-023"></span>**Teams must communicate in as many ways as possible—informally by telephone, formally by regular technical briefings, and structurally through a project workbook that imposes organization on all documents the project produces anyway.**
    - The OS/360 project workbook grew to five feet thick with 100 copies in Manhattan's Time-Life Building; daily change distributions averaged two inches of new pages to interfile, consuming significant time until the project switched to microfiche, saving a million dollars.
    - Critical importance attaches to timely updating, marking changed text with margin bars, and distributing a separately written change summary with each update—so readers know both what changed and what the current definition is.
* <span id="the-mythical-man-month-essays-on-software-engineer-024"></span>**Every project subtree needs both a producer (who assembles team, divides work, manages resources and schedule, communicates externally) and a technical director (who conceives and owns the design, ensures conceptual integrity, and communicates primarily internally)—roles requiring different talents that may be combined only in very small teams.**
    - Three viable arrangements exist: producer and director as the same person (workable only for 3–6 programmers); producer as boss with director as right-hand technical authority; or director as boss with producer handling all administrative burden—all three are found in successful practice.
    - Robert Heinlein's fictional illustration in 'The Man Who Sold the Moon' captures the director-as-boss arrangement: Harriman removes all administrative burden from the brilliant Coster, installs Berkeley as 'Lord High Everything Else,' and the engineering chief is freed for pure technical work.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Life_gears-mechanism.png" alt="" role="presentation" loading="lazy"></div>

## Calling the Shot

Actual software productivity data from multiple large projects consistently show that effort scales superlinearly with program size, that programmers spend only about half their time on actual programming, that complexity type (operating system vs. compiler) produces order-of-magnitude productivity differences, and that high-level languages can multiply productivity by a factor of five.

* <span id="the-mythical-man-month-essays-on-software-engineer-025"></span>**Software effort grows as approximately the 1.5 power of program size even without communication overhead—extrapolating sprint rates for small programs to large systems, like inferring a four-minute mile from a 100-yard dash, yields absurd predictions.**
    - Studies by Nanus and Farr at System Development Corporation and by Weinwurm both show an exponent near 1.5: effort = (constant) × (number of instructions)^1.5.
    - Sackman, Erikson, and Grant report a small program (3200 words) taking 178 hours with extrapolated productivity of 35,800 statements/year—but a program half that size took less than one-quarter as long, suggesting the extrapolation has no validity for large systems.
* <span id="the-mythical-man-month-essays-on-software-engineer-026"></span>**Portman's ICL data reveal that programming teams miss schedules by roughly half because they apply only about 50 percent of their working week to actual programming—the estimating error was entirely accounted for by unrealistic assumptions about technical work hours.**
    - Machine downtime, higher-priority short unrelated jobs, meetings, paperwork, company business, sickness, and personal time each consume small amounts, but together account for half the working week.
* <span id="the-mythical-man-month-essays-on-software-engineer-027"></span>**Task complexity drives order-of-magnitude productivity differences: Harr's Bell Labs data shows control programs achieving ~600 debugged words per man-year, language translators ~2200 words per man-year, and Aron's IBM data confirms the pattern across nine large systems.**
    - OS/360 experience confirms Harr's data: 600–800 debugged instructions/man-year for control programs, 2000–3000/man-year for language translators—and compilers are three times as hard as normal batch applications, operating systems three times as hard as compilers.
    - Corbatò's MIT Project MAC MULTICS data show 1200 lines of debugged PL/I per man-year—but each PL/I statement corresponds to three to five words of assembly language, suggesting productivity is constant in elementary statements and high-level languages multiply productivity by up to five times.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Space_orbit-arrow.png" alt="" role="presentation" loading="lazy"></div>

## Ten Pounds in a Five-Pound Sack

Program space is a major cost that must be actively managed through explicit size and disk-access budgets tied to precise functional allocations, but ultimately lean programs result not from tactical cleverness but from strategic breakthroughs—especially in data representation—which is the true essence of programming.

* <span id="the-mythical-man-month-essays-on-software-engineer-028"></span>**Size budgets must cover not just resident memory but all disk accesses occasioned by program fetches, and must be tied to exact functional definitions—OS/360's failure to do either produced disastrous performance and security violations.**
    - When the OS/360 performance simulator first ran, it showed Fortran H on a Model 65 compiling at five statements per minute—traced to control program modules each making many disk accesses, analogous to page thrashing, because only core sizes were budgeted, not disk accesses.
    - Because space budgets were set before precise functional allocations, programmers in size trouble threw buffers and control blocks over the fence into neighbors' space, compromising security and protection of the entire system.
* <span id="the-mythical-man-month-essays-on-software-engineer-029"></span>**A team-orientation breakdown in large projects causes each subteam to suboptimize its own targets rather than think about total user effect—the most important function of the programming manager is fostering a total-system, user-oriented attitude.**
    - The project was large enough and management communication poor enough that many team members saw themselves as contestants making brownie points rather than builders making programming products—a major hazard of large projects.
* <span id="the-mythical-man-month-essays-on-software-engineer-030"></span>**Lean, fast programs almost always result from strategic breakthrough in data representation rather than tactical cleverness—showing the flowcharts conceals a program's essence, while showing the tables makes it obvious.**
    - A young IBM 650 programmer packed an elaborate console interpreter into incredibly small space by building an interpreter for the interpreter—recognizing that human interactions are slow but space was dear.
    - Digitek's Fortran compiler used a dense, specialized representation for the compiler code itself, avoiding external storage; time lost in decoding was gained back tenfold by avoiding input-output.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Life_tower-antenna.png" alt="" role="presentation" loading="lazy"></div>

## The Documentary Hypothesis

A small set of written documents—covering objectives, specifications, schedule, budget, organization, and space allocation—form the critical management tools for any project, because the act of writing forces the hundreds of mini-decisions that distinguish clear policies from fuzzy ones, and the documents then serve as communication devices and status checklists.

* <span id="the-mythical-man-month-essays-on-software-engineer-031"></span>**Every management task—computer product, university department, software project—requires the same small set of critical documents covering what, when, how much, where, and who; their structure is universal because managerial concerns are universal.**
    - For a software project: objectives, product specifications (beginning as a proposal and ending as manual and internal documentation), schedule, budget, space allocation, and organization chart—where Conway's Law predicts the organization chart will initially reflect the first system design.
    - "Conway's Law: 'Organizations which design systems are constrained to produce systems which are copies of the communication structures of these organizations'—so if the system design must be free to change, the organization must be prepared to change." —Conway
* <span id="the-mythical-man-month-essays-on-software-engineer-032"></span>**Writing decisions down is essential not primarily for communication but because the act of writing exposes gaps, inconsistencies, and forces the hundreds of mini-decisions that distinguish clear, exact policies from fuzzy ones.**
    - Only a small part—perhaps 20 percent—of the executive's time is spent on tasks where he needs information from outside his head; the rest is communication: hearing, reporting, teaching, exhorting, counseling, encouraging.
    - The project manager's fundamental job is to keep everybody going in the same direction; his chief daily task is communication, not decision-making, and documents immensely lighten this load.


<div class="chapter-glyph"><img src="/glyphs/Business & Economics/Life_group-people.png" alt="" role="presentation" loading="lazy"></div>

## Plan to Throw One Away

Because the first system built will always need redesign—as requirements evolve, technology shifts, and implementation reveals flaws invisible in planning—the only question is whether to plan for a throwaway pilot or deliver it to customers, and program maintenance itself is an entropy-increasing process that inevitably destroys structure until ground-up redesign becomes necessary.

* <span id="the-mythical-man-month-essays-on-software-engineer-033"></span>**Chemical engineers always build a pilot plant between lab and factory; software engineers rarely do, but all large-system experience shows that the first system built is barely usable and will be redesigned—the management question is only whether to plan for it or deliver the throwaway to customers.**
    - Delivering the throwaway to customers buys time at the cost of agony for the user, distraction for builders during redesign, and a bad reputation for the product that the best redesign will find hard to live down.
* <span id="the-mythical-man-month-essays-on-software-engineer-034"></span>**Both actual user needs and the user's perception of those needs change as programs are built and used, so designing for change through modularization, table-driven techniques, high-level language, and numbered version releases is not optional but essential.**
    - The tractability and invisibility of software expose its builders to perpetual changes in requirements—unlike physical products where the existence of a tangible object serves to contain and quantize user demand for changes.
    - Programmer reluctance to document designs comes not from laziness but from hesitancy to commit to defending decisions the designer knows are tentative—so organizational structure that is threatening will prevent documentation until everything is defensible.
* <span id="the-mythical-man-month-essays-on-software-engineer-035"></span>**Program maintenance has a 20–50% chance of introducing a new bug with each fix, requires regression testing the entire test bank after every change, and totals 40% or more of development cost—while the number of users strongly affects maintenance cost because more users find more bugs.**
    - Campbell's data from MIT's Laboratory for Nuclear Science show a drop-and-climb curve in bug rate over a product's life: initial shakeout, a stable period, then rising bugs as users reach a new plateau of sophistication and exercise new capabilities fully.
    - The repairer is usually not the original author—often a junior programmer—and tends to fix only the local, obvious symptom while overlooking system-wide ramifications, producing the 'two steps forward, one step back' phenomenon.
* <span id="the-mythical-man-month-essays-on-software-engineer-036"></span>**Lehman and Belady's study of successive OS/360 releases shows that the number of affected modules grows exponentially with release number—all repairs increase entropy and disorder until the system subsides into unfixable chaos requiring ground-up redesign.**
    - Systems program building is an entropy-decreasing process, hence inherently metastable; program maintenance is an entropy-increasing process, and even the most skillful execution only delays the subsidence of the system into unfixable obsolescence.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Space_orbit-with-rocket.png" alt="" role="presentation" loading="lazy"></div>

## Sharp Tools

Effective software project tools require a philosophy that balances shared common tools (which improve communication) with specialized team tools (which improve individual productivity), with the most powerful tools being high-level languages and interactive programming—each of which improves productivity by an integral factor, not merely an incremental percentage.

* <span id="the-mythical-man-month-essays-on-software-engineer-037"></span>**Target machine scheduling is most productive when allocated in substantial blocks to one subteam at a time—allowing ten shots in a six-hour block rather than ten shots spaced three hours apart, because sustained concentration reduces thinking time—a practice confirmed over 20 years of technology change.**
    - OS/360 development initially used centralized batch scheduling for all 16 systems, but after months of slow turnaround and recriminations, switched to allocating whole machine blocks to subteams, dramatically improving productivity even if machine utilization was slightly lower.
    - System debugging has always been a graveyard-shift occupation, like astronomy—the predawn hours, when machine-room bosses are home and operators are disinclined to be sticklers for rules, remain most productive across three machine generations.
* <span id="the-mythical-man-month-essays-on-software-engineer-038"></span>**A master program library with three separated sublibrary tiers—individual playpens, integration library (under integration manager control), and released version (sacrosanct)—provides the control and formal progression essential for team software building.**
    - The W. R. Crowley library system on OS/360 used two 7010s sharing a large disk bank: each programmer owned his playpen, but passing a component to integration transferred control to the integration manager who alone could authorize changes.
    - This management technology was independently developed on several massive programming projects including Bell Labs, ICL, and Cambridge University—suggesting it is a discovered necessity rather than a designed innovation.
* <span id="the-mythical-man-month-essays-on-software-engineer-039"></span>**High-level language improves productivity by integral factors (not percentages) and improves debugging by reducing bugs and making them easier to find—the classical objections of function, object-code space, and speed have been made obsolete by advances in compiler technology.**
    - Corbatò's MULTICS data showing 1200 debugged PL/I lines per man-year—equivalent to 3600–6000 assembly language words—is the strongest evidence that programming productivity may be increased as much as five times with a suitable high-level language.
    - One can usually solve remaining speed problems by replacing 1–5% of compiler-generated code with handwritten substitute after the former is fully debugged, making the speed objection no longer fatal.
* <span id="the-mythical-man-month-essays-on-software-engineer-040"></span>**Interactive programming at least doubles productivity in system programming by eliminating the interruption of consciousness inherent in batch turnaround, which causes programmers to forget the context and thrust of complex problems between runs.**
    - Harr's Bell Labs data suggest an interactive facility at least doubles productivity in system programming—consistent with the logic that debugging is the hard part of system programming, and slow turnaround is the bane of debugging.


<div class="chapter-glyph"><img src="/glyphs/Business & Economics/Earth_figure-working.png" alt="" role="presentation" loading="lazy"></div>

## The Whole and the Parts

Building a working system requires designing bugs out through conceptual integrity and top-down stepwise refinement, disciplined component debugging before system integration, heavy use of test scaffolding, strict change control, and one-component-at-a-time system integration—because system debugging is always harder and longer than expected.

* <span id="the-mythical-man-month-essays-on-software-engineer-041"></span>**The most pernicious bugs are system bugs from mismatched assumptions among component authors; Vyssotsky's observation that 'many failures concern exactly those aspects that were never quite specified' argues for having an outside testing group scrutinize specifications for completeness and clarity before any code is written.**
    - "Developers themselves cannot test their own specifications for clarity: 'They won't tell you they don't understand it; they will happily invent their way through the gaps and obscurities.'" —V. A. Vyssotsky
    - Conceptual integrity of the product not only makes it easier to use, it makes it easier to build and less subject to system bugs.
* <span id="the-mythical-man-month-essays-on-software-engineer-042"></span>**Top-down design by stepwise refinement—sketching rough task and solution, then progressively elaborating both definition and algorithm while suppressing detail until necessary—is the most important new programming formalization of the decade, avoiding bugs by making structural flaws apparent at each refinement level.**
    - Niklaus Wirth's 1971 paper formalized what the best programmers had practiced for years: identify design as a sequence of refinement steps, with each refinement in task definition accompanied by a refinement in algorithm and data representation.
    - Top-down design allows testing at each refinement step so testing can start earlier; it makes flaws in structure more apparent; and it reduces the temptation to salvage a bad basic design with cosmetic patches.
* <span id="the-mythical-man-month-essays-on-software-engineer-043"></span>**System debugging requires beginning only with debugged components, building extensive scaffolding (perhaps half as much code as the product), controlling all changes through a single authority, adding one component at a time, and quantizing updates to prevent the test bed from shifting under the teams building on it.**
    - The 'bolt-it-together-and-try' approach, which assumes component testing scaffolding can be avoided by using pieces to test each other, is consistently wrong—using clean, debugged components saves much more time in system testing than that spent on scaffolding.
    - Lehman and Belady offer evidence that change quanta should be very large and widely spaced or else very small and frequent; the latter is more subject to instability, and large infrequent updates are the safer practice in system debugging.


<div class="chapter-glyph"><img src="/glyphs/Business & Economics/Earth_gears-machinery.png" alt="" role="presentation" loading="lazy"></div>

## Hatching a Catastrophe

Projects become a year late one day at a time through imperceptible daily slippage that no one recognizes as a crisis; the remedy is knife-edged concrete milestones, PERT critical-path scheduling to identify which slips matter, and a management culture that separates status review from problem-action so that first-line managers report honest status rather than concealing problems.

* <span id="the-mythical-man-month-essays-on-software-engineer-044"></span>**Milestones must be concrete, specific, measurable 100-percent events—not vague phases like 'coding 90% complete' or 'planning complete'—because a sharp milestone cannot be self-deceived, and a programmer will rarely lie about progress he cannot fudge.**
    - Studies of government contractor estimating behavior show that activity time estimates revised every two weeks do not significantly change as start time approaches, that during the activity overestimates come steadily down, but that underestimates do not change significantly until about three weeks before scheduled completion.
    - Chronic schedule slippage is a morale-killer because it deceives everyone about lost time until it is irremediable—making the fuzzy milestone a millstone, not just a failing.
* <span id="the-mythical-man-month-essays-on-software-engineer-045"></span>**A PERT critical-path chart is the only tool that answers which slips matter—showing who waits for what, how much an activity can slip before reaching the critical path—and its preparation, not just its use, forces specific early planning.**
    - The first PERT chart is always terrible, and one invents and invents in making the second one—but the network forces a great deal of very specific planning very early in the project.
    - Hustle—running faster than necessary, moving sooner than necessary—is essential for great programming teams as for great baseball teams; it provides the reserve capacity to cope with routine mishaps and forfend minor calamities.
* <span id="the-mythical-man-month-essays-on-software-engineer-046"></span>**First-line managers systematically conceal slippage from bosses because they fear the boss will preempt their function—the solution is to explicitly separate status-review meetings from problem-action meetings, and to accept status without panic so that honest reporting becomes safe.**
    - "Vyssotsky recommends carrying both 'scheduled' (boss's dates) and 'estimated' (lowest-level manager's dates) in milestone reports—the project manager must keep his fingers off the estimated dates and emphasize accurate, unbiased estimates over optimistic or self-protective ones." —V. Vyssotsky
    - A small Plans and Controls team (one to three people) that handles all the paperwork for the PERT chart reduces the burden on line managers to the essentials—making decisions—while serving as the early warning system against losing a year one day at a time.


<div class="chapter-glyph"><img src="/glyphs/Business & Economics/Earth_gears-machinery.png" alt="" role="presentation" loading="lazy"></div>

## The Other Face

A program product has two faces—one to the machine and one to the human user—and the latter requires not exhortation but demonstration of how to document effectively; self-documenting programs that incorporate documentation into source structure, naming, and formatted comments minimize the maintenance burden while maximizing accuracy.

* <span id="the-mythical-man-month-essays-on-software-engineer-047"></span>**Most documentation fails by giving too little overview—describing bark and leaves without a map of the forest—and effective user documentation requires nine elements presented from broad purpose down to precise details, drafted before the program is built since it embodies basic planning decisions.**
    - The nine required documentation elements: purpose, environment, domain and range, functions and algorithms, input-output formats, operating instructions, options, running time, and accuracy and checking methods—often achievable in three or four pages.
    - To believe a program works, users need test cases in three parts: mainline cases testing chief functions, barely legitimate cases probing the domain edge, and barely illegitimate cases ensuring invalid inputs produce proper diagnostics.
* <span id="the-mythical-man-month-essays-on-software-engineer-048"></span>**The detailed flow chart is an obsolete nuisance—a high-level language already does what flow charts did (group machine instructions into meaningful clusters), leaving only GO TOs, which structured programming minimizes—and no experienced programmer routinely makes detailed flow charts before writing programs.**
    - When introduced by Goldstine and von Neumann, flow chart boxes served as a high-level language grouping inscrutable machine-language statements; in a systematic high-level language the clustering is already done, and the boxes become a tedious drafting exercise.
    - Machine-generated flow charts from completed code—a practice common in shops requiring them—is not a deplorable departure from good practice but the application of good judgment, revealing that detailed flow charts are not a useful design tool.
* <span id="the-mythical-man-month-essays-on-software-engineer-049"></span>**Self-documenting programs—which merge documentation into source code via mnemonic names, declarations used as legends, space and indentation to show structure, and prose paragraph comments—solve the maintenance problem because documentation that lives in the source program cannot fall out of sync with it.**
    - The basic principle from data processing—never maintain independent files in synchronism, combine them into one—applies directly: maintaining a machine-readable program and a separate human-readable document inevitably produces documentation that doesn't accurately reflect changes.
    - Key techniques include using a program name containing a version identifier, incorporating prose description as comments to the PROCEDURE statement, referring to standard literature for algorithms, and declaring all variables with comments converting declarations into a complete legend of purpose.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Space_satellite-orbit.png" alt="" role="presentation" loading="lazy"></div>

## No Silver Bullet—Essence and Accident in Software Engineering

Software's essential difficulties—complexity, conformity to arbitrary external interfaces, constant changeability, and invisibility—are inherent in the nature of software itself, not in tools or processes, so no single technological development can produce an order-of-magnitude improvement; past breakthroughs (high-level languages, time-sharing, unified environments) each attacked only accidental difficulties, and the same limit applies to Ada, OOP, AI, and graphical programming.

* <span id="the-mythical-man-month-essays-on-software-engineer-050"></span>**Software's complexity is essential, not accidental—because no two parts are alike (otherwise they'd be one subroutine), scaling up means increasing the number of different elements with nonlinear interactions, and this complexity cannot be abstracted away without abstracting away the essence itself.**
    - From complexity comes difficulty of communication among team members (leading to product flaws), difficulty of enumerating all possible program states (leading to unreliability), difficulty of invoking functions (making programs hard to use), and unvisualized states constituting security trapdoors.
    - Mathematics and physics made great strides by constructing simplified models of complex phenomena—but that works only when the ignored complexities are not essential properties. It does not work when the complexities are the essence.
* <span id="the-mythical-man-month-essays-on-software-engineer-051"></span>**Software must conform to arbitrary external interfaces designed by different people at different times, not to any unifying principle—making much of its complexity irreducible through any redesign of the software alone.**
    - Unlike physics, which works in faith that unifying principles like quarks or unified field theories will emerge, software engineers face complexity imposed without rhyme or reason by the many human institutions to which their interfaces must conform.
* <span id="the-mythical-man-month-essays-on-software-engineer-052"></span>**High-level languages, time-sharing, and unified programming environments like Unix each gave integral-factor improvements by attacking accidental difficulties—but each has a natural ceiling, and further accidental difficulties are smaller, making future gains from this approach inherently marginal.**
    - High-level language frees programs from their accidental complexity of bits, registers, and branches; time-sharing preserves immediacy and avoids the decay of grasp over complex systems caused by batch interruption; Unix and Interlisp attacked using programs together by providing integrated libraries and uniform file formats.
    - Time-sharing's principal benefit is reducing system response time; once it passes below the human threshold of noticeability (~100 milliseconds), no further benefit is expected—showing the natural ceiling of this approach.
* <span id="the-mythical-man-month-essays-on-software-engineer-053"></span>**Ada, object-oriented programming, AI/expert systems, automatic programming, graphical programming, and program verification each address either accidental rather than essential difficulties, or address essential difficulties only marginally—none promises an order-of-magnitude improvement.**
    - Expert systems can disseminate good programming practice widely and put accumulated wisdom of the best programmers at the service of the inexperienced—valuable, but still limited by the difficulty of knowledge acquisition and the need to extract articulate, self-analytical experts.
    - "Parnas on automatic programming: 'In short, automatic programming always has been a euphemism for programming with a higher-level language than was presently available to the programmer'—the solution method, not the problem, must be specified." —Parnas
* <span id="the-mythical-man-month-essays-on-software-engineer-054"></span>**Promising genuine attacks on essential difficulty include buying instead of building (mass-market software), rapid prototyping for requirements refinement, incremental organic growth instead of waterfall construction, and cultivating great designers—because great designs come from great designers, not from sound methodology alone.**
    - The development of the mass market is the most profound long-run trend in software engineering: sharing development cost among many users radically cuts per-user cost, and using n copies of a software system effectively multiplies the productivity of its developers by n.
    - Harlan Mills's incremental development proposal—where the system is first made to run (even as dummy stubs), then fleshed out function by function, so there is always a working system—showed the most dramatic results in Brooks's software engineering laboratory, with teams growing more complex entities in four months than they could build.
    - The differences between great and average designers approach an order of magnitude; software systems that excited passionate fans—Unix, APL, Pascal, Smalltalk—are products of one or a few designing minds, in contrast to Cobol, PL/I, MVS/370, and MS-DOS.


<div class="chapter-glyph"><img src="/glyphs/Business & Economics/Life_money-100-bill.png" alt="" role="presentation" loading="lazy"></div>

## "No Silver Bullet" Refined

Nine years of response to 'No Silver Bullet' confirms the central argument—the accidental part of software work is now less than half the total, making magical productivity gains impossible—while clarifying that the essential difficulties of complexity, conformity, changeability, and invisibility can be ameliorated though not eliminated, especially through object-oriented techniques, reuse, and growing software incrementally.

* <span id="the-mythical-man-month-essays-on-software-engineer-055"></span>**The truthfulness of 'No Silver Bullet' reduces to an empirical question: what fraction of software effort is now accidental (representational) versus essential (conceptual)? Brooks estimates the accidental part at less than half, and no correspondent has publicly asserted it is as large as nine-tenths—making an order-of-magnitude gain from eliminating accidentals mathematically impossible.**
    - Herzberg, Mausner, and Sayderman's 1959 motivational research finds that positive environmental factors cannot increase productivity but negative ones can decrease it—consistent with 'NSB's' argument that removing negative accidental factors (awkward machine languages, batch processing, poor tools) has driven past progress.
* <span id="the-mythical-man-month-essays-on-software-engineer-056"></span>**Object-oriented programming has grown slowly despite promise because programmers built low-level classes (linked-list, set) rather than domain-level classes (user-interface, radiation-beam), and because OO involves severe front-loaded costs (retraining, building generalized classes) with back-loaded benefits (faster fifth and later projects in a family).**
    - "Coggins: 'Object-oriented techniques will not make the first project development any faster, or the next one. The fifth one in that family will go blazingly fast'—the extreme cost front-loading and benefit back-loading is the largest single factor slowing OO adoption." —James Coggins
    - "Parnas argues the slow adoption is simpler: 'It has been tied to a variety of complex languages. Instead of teaching people that O-O is a type of design and giving them design principles, people have taught that O-O is the use of a particular tool.'" —David Parnas
* <span id="the-mythical-man-month-essays-on-software-engineer-057"></span>**Real software reuse remains limited because the vocabulary problem is underappreciated—higher-level programming languages and class libraries have larger vocabularies that must be learned, and learning 3000+ class interfaces is a substantial intellectual barrier that the discipline has not yet addressed systematically.**
    - Van Snyder of JPL argues that mathematical software has achieved reuse for two reasons: it is arcane (high cost to reconstruct) and has a rich standard nomenclature (low cost to discover what an existing component does)—conditions not generally met in other software domains.
    - "DeMarco: 'I am becoming very discouraged about the whole reuse phenomenon. There is almost a total absence of an existence theorem for reuse. Time has confirmed that there is a big expense in making things reusable.'" —Tom DeMarco
* <span id="the-mythical-man-month-essays-on-software-engineer-058"></span>**Harel's 'Biting the Silver Bullet' thought experiment—reimagining 'NSB' as written in 1952—fails because it mischaracterizes the state of software in the 1950s, where large systems (SAGE's 75,000-instruction real-time system, GE's 80,000-word payroll system) were already in operation and team-scale software challenges already existed.**
    - Jones's key insight: focus on quality, and productivity will follow—costly, late projects invest most of their extra work and time in finding and repairing errors in specification, design, and implementation; systematic quality controls prevent the bulk of the schedule disaster.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Space_satellite-orbit.png" alt="" role="presentation" loading="lazy"></div>

## Propositions of The Mythical Man-Month: True or False?

This chapter presents, in stark outline form, all the key factual assertions and rules of thumb from the original 1975 edition—covering the nine-times cost of programming systems products, Brooks's Law, scheduling ratios, productivity data, documentation principles, and management practices—as testable propositions for readers to evaluate against current evidence.

* <span id="the-mythical-man-month-essays-on-software-engineer-059"></span>**The core economic and productivity propositions from 1975 remain the anchors of the book: a programming systems product costs nine times as much as a privately used program, programmers are ten times as productive as poor ones at the same experience level, and adding manpower to a late project makes it later.**
    - Proposition 1.1: Productizing imposes a factor of three (generalization, testing, documentation); systemizing imposes another factor of three (interface conformance, resource budgets, integration testing); these are independent, so the product costs nine times the component program.
    - Proposition 2.11: Brooks's Law—adding manpower to a late software project makes it later—plus the mechanism: repartitioning work, training new people, and added intercommunication each add to total effort.
* <span id="the-mythical-man-month-essays-on-software-engineer-060"></span>**Several 1975 propositions are explicitly identified as now obsolete or superseded: PL/I as 'the only reasonable candidate for system programming' is no longer true; the size of transient areas as a crucial decision has been made obsolete by virtual memory and cheap real memory; high-level language and interactive programming are now universally adopted rather than resisted.**
    - Proposition 7.15 is explicitly reversed: 'Parnas argues strongly that the goal of everyone seeing everything is totally wrong; parts should be encapsulated. . . . I have been quite convinced otherwise by Parnas, and totally changed my mind.'
    - Proposition 8.4 notes that Boehm's data do not agree with the 1.5 exponent for effort scaling, finding instead exponents varying from 1.05 to 1.2 across his dataset.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Space_satellite-orbit.png" alt="" role="presentation" loading="lazy"></div>

## The Mythical Man-Month after 20 Years

Twenty years of subsequent experience confirm the book's central arguments about conceptual integrity and the architect, while requiring major revisions: the waterfall model is wrong and should be replaced by incremental build, Parnas was right about information hiding and Brooks was wrong, the microcomputer revolution has transformed both how software is used and built, and the most important new trend is shrink-wrapped mass-market software that buys what formerly had to be built.

* <span id="the-mythical-man-month-essays-on-software-engineer-061"></span>**Conceptual integrity remains the most important factor in software product quality, requiring a designated architect as the user's agent who owns the public mental model of the product—a conclusion more strongly held after 20 years, now advocated even for four-person student teams.**
    - The architect role differs from the team manager role as director differs from producer in a film: the architect is responsible for the conceptual integrity of all aspects perceivable by the user, while the manager handles resources, schedule, and external communication.
    - For large products, the master architect partitions the system at subsystem boundaries where interfaces are minimal and easiest to define rigorously, with each subsystem having its own architect—creating a recursive hierarchy of architectural authority.
* <span id="the-mythical-man-month-essays-on-software-engineer-062"></span>**The waterfall model is fundamentally wrong because it assumes one goes through the construction process only once and that user testing can wait until the end—the correct model is incremental build, where the system first runs as stubs, then is fleshed out function by function, so there is always a working, testable system.**
    - Harlan Mills advocated building the basic polling loop with null subroutines first, compiling and testing it—then incrementally adding and fleshing out modules while maintaining a working system at every stage, enabling early user testing and build-to-budget strategies.
    - Microsoft's 'build every night' approach carries incremental build to its logical conclusion: the developing system is rebuilt nightly, the build cycle is the heartbeat of the project, and if the build breaks the whole process stops until the trouble is fixed—giving the team credibility and morale through always knowing the true status.
* <span id="the-mythical-man-month-essays-on-software-engineer-063"></span>**Brooks explicitly reverses his 1975 dismissal of Parnas's information hiding: Parnas was right, Brooks was wrong—information hiding embodied in object-oriented programming is the only way of raising the level of software design, enabling programs to be built by composing prebuilt, tested, documented modules at a higher conceptual level.**
    - Parnas defined a module as a software entity with its own data model and operations, whose data can only be accessed via proper operations—the first step in a program of raising the conceptual level of software building that led to abstract data types and then to OOP with inheritance.
    - Many people vainly hope for significant module reuse without paying the initial cost of building product-quality modules—generalized, robust, tested, and documented—but the ratio of reusable module cost to one-shot module cost is roughly threefold, matching the productizing factor from Chapter 1.
* <span id="the-mythical-man-month-essays-on-software-engineer-064"></span>**Boehm's COCOMO model solidly confirms that the man-month is mythical—the optimum schedule goes as the cube root of man-months of effort, cost rises sharply below optimum schedule, and hardly any projects succeed in less than 3/4 of the calculated optimum schedule regardless of manpower applied.**
    - Boehm's model finds that the quality of the team is by far the largest factor in project success—four times more potent than the next largest factor—confirming that people are everything, or almost everything.
    - Abdel-Hamid and Madnick's careful model shows that adding manpower always makes a late project more costly but does not always make it later—adding people early is much safer than adding them late, since new people have an immediate negative effect that takes weeks to compensate.
* <span id="the-mythical-man-month-essays-on-software-engineer-065"></span>**The WIMP interface (Windows, Icons, Menus, Pointing) is the most impressive software achievement of the two decades—a superb example of conceptual integrity achieved through a consistent desktop metaphor, and enforced across third-party applications by building the interface into ROM so that using it was easier than building a proprietary alternative.**
    - The Mac's direct incorporation of the interface into ROM enforced a de facto standard across third-party applications: developers used it because it was easier and faster, and product reviewers mercilessly criticized non-conforming products—demonstrating the power of the technique recommended in Chapter 6.
    - The one-cursor/menu design makes the cursor do the work of two—alternating between data-space and menu-space, discarding locality information each time—but the keyboard shortcut system provides an elegant dual path from novice (menu) to power user (chord shortcuts) with smooth incremental transition.
* <span id="the-mythical-man-month-essays-on-software-engineer-066"></span>**The microcomputer revolution and shrink-wrapped software industry are the crucial changes of the two decades—making computing accessible, cheap, and compatible with human creativity, while creating a new paradigm where mass-market packages serve as tested, documented modules on which richer customized products are built through metaprogramming.**
    - Schumacher's challenge of 20 years earlier—equipment cheap enough for everyone, suitable for small-scale application, compatible with human creativity—was exactly fulfilled by the microcomputer revolution, giving ordinary people self-expression tools in drawing, music, writing, photography, and video.
    - Building-on-packages (truck tracking on a shrink-wrapped database, Excel templates, Hypercard stacks) attacks the essence of software construction by providing large, documented, tested modules whose internal conceptual structure need not be designed at all—a secondary market in reusable metaprograms that grew up unremarked.
