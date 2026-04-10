---
title: "The Art of Doing Science and Engineering: Learning to Learn"
sortTitle: "Art of Doing Science and Engineering: Learning to Learn"
date: 2026-04-10
slug: "the-art-of-doing-science-and-engineering"
draft: false
dateAdded: 2026-04-10
description: "Excellence in science and engineering requires cultivating a deliberate 'style' of thinking—combining technical fundamentals, broad curiosity, and visionary goal-setting—rather than merely accumulating technical knowledge. The future belongs to those who prepare their minds, embrace change, and work on important problems with courage and clarity."
bookKeywords: "style of thinking and intellectual preparation, history and future of computing and information technology, mathematics as a tool for clear thinking, creativity, expertise, and the structure of scientific progress, engineering judgment under uncertainty"
author: "Richard W. Hamming"
shortAuthor: "Hamming"
year: "1997"
tags: ["science", "education", "technology & engineering"]
collections: ["Terraform Industries"]
---



## Orientation

The course is not about technical content but about cultivating a 'style of thinking' suited to a future where knowledge doubles every 17 years, requiring individuals to develop a personal vision, master fundamentals, and commit to doing significant rather than merely competent work. Hamming argues that a career guided by vision travels a distance proportional to n rather than the random-walk distance of √n.

* <span id="the-art-of-doing-science-and-engineering-learning--001"></span>**Education (what and why) differs fundamentally from training (how), and both are necessary; this course focuses on education in the form of meta-education—examining how to think rather than what to think.**
    - Education is what, when, and why to do things; training is how to do it.
    - The course is compared to studying under a master painter: you learn style and must forge your own, adapted to the future.
* <span id="the-art-of-doing-science-and-engineering-learning--002"></span>**Knowledge has doubled every 17 years since Newton's time, meaning the technical knowledge a person faces will quadruple in roughly 34 years—making the ability to learn new fields continuously more important than any specific current knowledge.**
    - Back-of-the-envelope calculation shows the two claims—knowledge doubling every 17 years and 90% of scientists being alive today—are mutually consistent under a simple exponential growth model.
    - The half-life of technical knowledge learned in school is about 15 years, making continuous self-education essential.
* <span id="the-art-of-doing-science-and-engineering-learning--003"></span>**Back-of-the-envelope calculations are a hallmark of great scientists because they quickly reveal whether quantitative claims are plausible, keep modeling skills sharp, and help avoid accepting nonsense presented in media or public discourse.**
    - Hamming regularly used such calculations at the physics lunch table to correct misconceptions in real time.
    - The first pass uses definite numbers; the second uses parameters to understand the general case.
* <span class="pull-quote">No vision, not much of a future.</span>
* <span id="the-art-of-doing-science-and-engineering-learning--004"></span>**Science and engineering are converging: science is what you do when you don't yet know what you're doing, engineering when you must know—but the accelerating pace of progress leaves no leisure to keep the fields separate, and much future knowledge will be created after you leave school.**
    - In science, if you know what you are doing, you should not be doing it. In engineering, if you do not know what you are doing, you should not be doing it.
    - Applied science is a distinct third field between science and engineering, often unrecognized.
* <span id="the-art-of-doing-science-and-engineering-learning--005"></span>**A career with a clear vision travels a distance proportional to n (number of decisions), while one without vision travels only √n—making the act of forming and committing to a vision perhaps the single most important career decision.**
    - Accuracy of the vision matters less than having one; many paths lead to greatness, and the key is directional consistency rather than perfect foresight.
    - Three distinct questions must be kept separate: what is possible (science), what is likely to happen (engineering), and what is desirable (ethics).
* <span id="the-art-of-doing-science-and-engineering-learning--006"></span>**Computers will dominate future technical careers, and their advantages over humans—in economics, speed, accuracy, reliability, bandwidth, freedom from boredom, and hostile-environment operation—are so overwhelming that the key question is not whether to use them but how to use them well.**
    - The standard departmental organization of knowledge conceals the homogeneity of knowledge and omits topics that fall between courses; one function of this course is to fill those gaps.
    - Hamming frames the course as 'religious' in the sense of urging students to aim for significant contributions rather than mere comfort.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_lunar-cycle-row.png" alt="" role="presentation" loading="lazy"></div>

## Foundations of the Digital (Discrete) Revolution

The shift from continuous to discrete signaling was driven by noise immunity, transistor and IC development, and the growing information economy—and the S-curve growth model reveals that single-processor von Neumann computers are approaching saturation, pointing toward parallel processing and the dominance of general-purpose chips over special-purpose ones.

* <span id="the-art-of-doing-science-and-engineering-learning--007"></span>**Discrete (digital) signaling replaced continuous (analog) signaling primarily because repeaters rather than amplifiers prevent noise accumulation, enabling transmission with remarkable fidelity without requiring exquisitely accurate components.**
    - In continuous signaling, a transcontinental telephone path might involve a total amplification factor of 10^120, requiring each amplifier to be built with extreme accuracy.
    - Error-detecting and error-correcting codes further defeat noise in digital systems.
* <span id="the-art-of-doing-science-and-engineering-learning--008"></span>**Integrated circuits eliminated the soldered-joint problem, reduced cost, increased speed through component proximity, and—combined with lower voltages—enabled the exponential improvement in computing described by Moore's Law-like trends.**
    - In 1992, interconnection costs ranged from 0.001 cent on a chip to 100 cents between frames, creating strong economic pressure to keep components close together.
    - The steady decrease in voltage and current levels has partially solved the heat dissipation problem.
* <span id="the-art-of-doing-science-and-engineering-learning--009"></span>**Most technological fields follow S-shaped growth curves—slow start, rapid rise, then saturation at physical limits—and the von Neumann single-processor computer is clearly on the saturation portion of its S-curve, as evidenced by the shift toward parallel processors.**
    - The simplest growth model, modified with a limiting factor L, produces the logistic equation, whose solution has a characteristic S-shape; more flexible models allow asymmetric curves.
    - Often a new innovation sets a field onto a new S-curve taking off near the saturation of the old one.
* <span class="pull-quote">It has rarely proved practical to produce exactly the same product by machines as we produced by hand.</span>
* <span id="the-art-of-doing-science-and-engineering-learning--010"></span>**Mechanization requires producing an equivalent product, not the identical one—and failure to redesign the product for machine production, rather than merely automating the existing process, is one of the most common and costly errors in technological transition.**
    - When accounting moved from hand to machine methods, the accounting system itself had to change; when fabrication moved from hand to machine, screws and bolts gave way to rivets and welding.
    - Field maintenance must be part of the original design of any complex system, not grafted on later.
* <span id="the-art-of-doing-science-and-engineering-learning--011"></span>**Computers have transformed both science (by shifting 90–99% of experiments to simulation) and engineering (by enabling design of unstable systems stabilized by real-time computer control), but carry the risk of a return to scholasticism—trusting models over direct observation of nature.**
    - Hamming told Bell Labs management in the late 1950s that simulation would eventually dominate real experiments, and was disbelieved—yet that is exactly what happened.
    - The risk is that we are now looking more and more in books (simulations) and less at nature—the same error Galileo corrected in the Middle Ages.
* <span id="the-art-of-doing-science-and-engineering-learning--012"></span>**General-purpose chips should almost always be preferred over special-purpose chips because other users bear the cost of debugging, documentation, and upgrades—and because the accelerating pace of technological obsolescence means special-purpose designs lock you into your first design.**
    - Ego satisfaction in having a special chip is a major reason organizations choose them despite the long-term economic disadvantages.
    - Computers are enabling a societal shift from a material-goods economy to an information-service economy, with fewer than 25% of workers handling material things projected for 2020.


<div class="chapter-glyph"><img src="/glyphs/Science/Earth_eye-target.png" alt="" role="presentation" loading="lazy"></div>

## History of Computers—Hardware

The history of computing hardware follows an S-curve from mechanical calculators through relay machines to electronic computers, with speed increasing from 1/20 operations per second to 10^9 FLOPS—and the handwriting on the wall for single-processor machines points toward parallel architectures, while the human scale of nanoseconds and picoseconds reveals hard physical limits.

* <span id="the-art-of-doing-science-and-engineering-learning--013"></span>**The history of digital computing stretches from prehistoric tally bones and Stonehenge through Napier's logarithms, Babbage's analytical engine, and punched-card machines to modern electronic computers—each step increasing computational power by orders of magnitude.**
    - Babbage's analytical engine, conceived before his difference engine was finished, anticipated the von Neumann architecture; a group in England constructed it from his drawings in 1992 and it worked as designed.
    - Punched-card computing was invented because the 1890 US Census was taking so long that the next one would begin before the previous one was finished—a practical crisis driving innovation.
* <span id="the-art-of-doing-science-and-engineering-learning--014"></span>**The ENIAC (1946) launched the electronic computer age, but the key conceptual breakthrough—internal programming—is often misattributed to von Neumann, who was only a consultant; Mauchly and Eckert's team discussed it before von Neumann joined, and Wilkes at Cambridge built the first usefully running internally programmed machine.**
    - A group of experts including Hamming believed 18 IBM 701s would saturate the market for years—a dramatic underestimate because they only imagined existing applications, not new ones.
    - Mauchly and Eckert gave an open course in 1946 on designing electronic computers, spawning dozens of independent machines built by attendees.
* <span id="the-art-of-doing-science-and-engineering-learning--015"></span>**Physical limits—the size of molecules (~1–3 angstroms), the speed of light (~1 foot per nanosecond in a wire), and heat dissipation—create hard upper bounds on single-processor von Neumann computers, explaining the S-curve saturation and the drive toward parallel architectures.**
    - At picosecond pulse rates, signal paths must be separated by less than 1/100 of an inch, making lumped-circuit analysis invalid and heat removal critical.
    - Los Alamos data fit the equation OPS = 3.585×10^9 / (1 + e^(-0.3(t-1943))), predicting a von Neumann saturation asymptote of about 3.585×10^9 operations per second.
* <span id="the-art-of-doing-science-and-engineering-learning--016"></span>**Computers process bits according to other bits with no inherent meaning—meaning is assigned by humans through interpretation—and this machine-level view is essential for debugging, even as it raises profound questions about whether humans are fundamentally different from machines.**
    - Democritus (~460 BC) said 'All is atoms and void'—the same reductionist view held by many physicists today about both computers and humans.
    - The Current Address Register (CAR) cycle—fetch, decode, execute, increment—captures the complete, myopic loop of computation with no global awareness.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_sun-burst.png" alt="" role="presentation" loading="lazy"></div>

## History of Computers—Software

Software history is the progressive liberation of programmers from machine-level details through assemblers, FORTRAN, monitors, and higher-level languages—each step resisted by professionals who saw the new tools as 'sissy stuff'—and programming remains closer to novel writing than classical engineering because the problem is often only discovered through the act of programming itself.

* <span id="the-art-of-doing-science-and-engineering-learning--017"></span>**Every major advance in software abstraction—symbolic assembly, relocatable programs, FORTRAN, monitors—was fiercely resisted by professional programmers who considered each new level of abstraction unworthy of a 'real' programmer, mirroring the shoemaker's-children pattern seen across all professions.**
    - When Hamming demonstrated symbolic assembly to ~100 IBM cafeteria users, only one person showed any interest.
    - FORTRAN was opposed on three sequential grounds: it can't be done; if done, it wastes machine time; if it works, no respectable programmer would use it.
* <span id="the-art-of-doing-science-and-engineering-learning--018"></span>**FORTRAN succeeded where logically superior languages like ALGOL failed because it was psychologically designed—it translated the familiar notation of school mathematics—while logically designed languages require humans to learn new ways of thinking they cannot easily adopt.**
    - APL is logically elegant but not fit for normal humans; a single letter change completely alters meaning, giving it almost no redundancy, while human language is 40–60% redundant for good reason.
    - Humans are unreliable and require redundancy in their tools; a language easy for the computer expert is not necessarily easy for non-experts who will do most future programming.
* <span id="the-art-of-doing-science-and-engineering-learning--019"></span>**Hamming's design of an interpretive language on the IBM 650 illustrates the deep principle that you can make any machine behave like any other machine by writing an interpreter—the meaning of instructions is defined entirely by the subroutines they call, not by the symbols themselves.**
    - By using ten decimal digits for a three-address floating-point virtual machine on a two-address fixed-point real machine, Hamming could produce nearly ten times the output of colleagues still coding in absolute binary.
    - This is precisely what Turing proved with the Universal Turing Machine, but it was not clearly understood until practitioners had done it repeatedly.
* <span id="the-art-of-doing-science-and-engineering-learning--020"></span>**Productivity improvements in programming over 30 years total roughly a factor of 90—from assemblers through C++, UNIX, and code reuse—yet this pales against machine speed improvements, because the fundamental bottleneck is the human animal as it is, not as we wish it were.**
    - Programmers vary in productivity from worst to best by more than a factor of ten; Hamming concluded the best policy is to pay good programmers very well and regularly remove poor ones.
    - The analogy between programming and novel writing is apt: both have large creative components, and just as you cannot engineer novels, you cannot fully engineer software.
* <span id="the-art-of-doing-science-and-engineering-learning--021"></span>**The 'first discoverer' seldom understands what they invented as clearly as later practitioners do, because creators must fight through confusion and darkness that obscures the clarity later workers enjoy once the path is open.**
    - Hamming acknowledges a friend's claim that Hamming himself does not understand error-correcting codes as well as later workers—and he admits the friend is probably right.
    - It has been said Newton was the last of the ancients and not the first of the moderns.


<div class="chapter-glyph"><img src="/glyphs/Science/Earth_tree-of-life-globe.png" alt="" role="presentation" loading="lazy"></div>

## History of Computer Applications

Computer applications evolved from pure number-crunching through engineering, military, and symbol-manipulation uses, each adding a new S-curve that maintained overall exponential growth—and the key insight driving Hamming's own productivity was recognizing he was in 'the mass production of a variable product,' which led directly to investing in software tools that paid off within a year.

* <span id="the-art-of-doing-science-and-engineering-learning--022"></span>**The ability to give effective public talks is not optional for scientists: Hamming diagnosed his fear of public speaking as a career liability and deliberately fixed it by accepting every invitation to speak, choosing topics the audience wanted to hear rather than topics dear to his own heart.**
    - His 'History of Computing to the Year 2000' talk, given around 1960 to IBM customers, launched a series that ran for years and forced him to keep abreast of computing trends.
    - A scientist must communicate in three forms: written papers and books, prepared public talks, and impromptu talks—lacking any one is a serious career drag.
* <span id="the-art-of-doing-science-and-engineering-learning--023"></span>**Computer applications followed successive S-curves—scientific computing, engineering computing, military, then symbol manipulation—each plateauing in turn while the next kept overall growth roughly exponential, with pattern recognition and virtual reality projected as the next major wave.**
    - Scientific computing at Bell Labs rose exponentially but then showed clear upper-curve flattening as the total scientist population and problem types were finite.
    - The first computers at Bell Labs were used nine-tenths in labs and one-tenth by computer—Hamming predicted the ratio would invert, and it did.
* <span id="the-art-of-doing-science-and-engineering-learning--024"></span>**Interactive computing, pioneered by attaching a small SDS 910 computer to the Brookhaven cyclotron, at least doubled the effective productivity of the expensive cyclotron by enabling real-time data display and early abort of flawed experimental runs.**
    - Getting a computer into a lab 'under one pretext' consistently changed both the problem being studied and what the computer was actually used for—the equivalent job, not the same old one.
    - Boeing's attempt to keep a single shared design database for aircraft design failed because optimization studies require a stable snapshot, not a continuously updated database.
* <span id="the-art-of-doing-science-and-engineering-learning--025"></span>**Recognizing oneself as engaged in 'the mass production of a variable product' was the key insight that led Hamming to invest a full man-year building software tools, which paid off within a year by enabling far more computation than solving each problem one at a time.**
    - In a rapidly changing field like software, if the payoff from a tool is not in the near future it will probably never pay off.
    - The Intel 4004 was born from the same insight: instead of making a special chip for each customer, make a general four-bit computer and program it for each job.


<div class="chapter-glyph"><img src="/glyphs/Science/Earth_fire-flame.png" alt="" role="presentation" loading="lazy"></div>

## Limits of Computer Applications—AI–I

Artificial intelligence is not a topic you can afford to ignore or to believe in uncritically—the question 'can machines think?' is so poorly defined that whichever position you adopt there is a compelling counterargument, and your answer will determine whether you lead or lag in the computerization of your field.

* <span id="the-art-of-doing-science-and-engineering-learning--026"></span>**Computers manipulate symbols, not information—we cannot define 'information' precisely enough to write a program for it—and AI's limits are therefore not primarily hardware limits but conceptual and definitional ones.**
    - The General Problem Solver, starting with ~5 rules, escalated over decades to 500, then 5,000, then 50,000 rules, suggesting no convergence to a general solution.
    - Expert systems face two problems: world-class experts in many fields are barely better than beginners, and experts use their subconscious and can only report conscious experience.
* <span id="the-art-of-doing-science-and-engineering-learning--027"></span>**The Turing test pragmatically sidesteps defining 'thinking' but violates scientific method by jumping to a hard problem; Hamming's alternative question—'what is the smallest program I would believe could think?'—eventually led him to suspect thinking is a matter of degree rather than a yes/no property.**
    - A Jesuit-trained engineer defined thinking as 'what humans can do and machines cannot'—honest but circular, and the same logic was used for organic chemistry before Wohler synthesized urea.
    - The hard AI position—that man is only a collection of molecules and therefore machines can do everything humans do—and the soft AI position both have legitimate logical support.
* <span id="the-art-of-doing-science-and-engineering-learning--028"></span>**Samuel's checkers program, which modified its own weighting parameters by playing one variant against another and promoting the winner, 'learned from experience' in a meaningful sense—and if you deny this because a program told it how to learn, you must confront whether your own education is fundamentally different.**
    - The program beat a Connecticut state checkers champion after iteratively improving its evaluation function through self-play.
    - A geometry-proving program discovered an elegant proof of the isosceles triangle theorem—comparing triangle ABC with triangle CBA—that its designers did not know and that showed apparent 'novelty.'
* <span id="the-art-of-doing-science-and-engineering-learning--029"></span>**A Mars exploration vehicle that must react in milliseconds to falling ground without waiting 20+ minutes for Earth instructions epitomizes why some degree of machine 'intelligence' is not optional but physically required for future high-speed autonomous systems.**
    - Modern fastest aircraft are fundamentally unstable and require computer stabilization millisecond by millisecond—no human pilot could handle this; the human supplies only high-level strategy.
    - The boredom factor makes humans unreliable for sustained vigilance—'piloting a plane is hours of boredom and seconds of sheer panic,' not something humans were designed for.


<div class="chapter-glyph"><img src="/glyphs/Education/Life_microscope-lens.png" alt="" role="presentation" loading="lazy"></div>

## Limits of Computer Applications—AI–II

Computers have demonstrably produced psychological novelty—surprising their own programmers—in domains from music composition to medical diagnosis to robot manufacturing, and the central unresolved question is whether the 'how' of doing something (not just the 'what') determines whether thinking has occurred.

* <span id="the-art-of-doing-science-and-engineering-learning--030"></span>**Computer-composed and computer-performed music is now technically perfect—any sound that can exist can be produced—shifting the question entirely from 'what can be done?' to 'what sounds are worth producing?', while also giving composers faster feedback that accelerates stylistic development.**
    - Max Mathews and John Pierce at Bell Labs pioneered computer music by reasoning from sampling theory: if you can compute the sound-track height at each time interval and smooth it, you have the music.
    - The conductor now has complete control down to millisecond timing and fraction-of-tone accuracy for each simulated instrument, eliminating the constraint that all musicians must be perfect simultaneously.
* <span id="the-art-of-doing-science-and-engineering-learning--031"></span>**Medical diagnosis by machine is technically superior to average doctors for rare diseases—machines don't forget and can hold all relevant diseases—but will be blocked for years by legal liability structures that forgive human error but make machine error prosecutable.**
    - With probabilities adjusted for current epidemics, machines can probably outperform the average doctor—and it is average doctors, not famous specialists, who must treat most people.
    - Every computer program sold explicitly absolves the seller of any responsibility for the product—the legal problems of new applications are often the main difficulty, not the engineering.
* <span id="the-art-of-doing-science-and-engineering-learning--032"></span>**Chess-playing programs approach world-champion level by examining millions of positions per second vs. humans' 50–100—solving the problem 'by volume of computation' rather than by insight—illustrating that AI research goals (understanding human thought) were perverted into merely winning games.**
    - The original purpose of game-playing AI research was to study human thought processes, not to win; this goal has been largely abandoned.
    - Go remains hard to program well despite simple rules, illustrating that problem difficulty for machines does not correlate with rule complexity.
* <span id="the-art-of-doing-science-and-engineering-learning--033"></span>**The distinction between logical novelty (genuinely new conclusions not derivable from premises) and psychological novelty (surprising results that are in fact logically entailed) suggests that all of mathematics beyond its axioms is technically only psychologically novel—yet this is not trivial.**
    - Programmers are constantly surprised by what their own programs do—machines produce psychological novelty routinely.
    - Perhaps thinking should be measured not by what you do but how you do it—watching a child multiply feels like thinking, doing the same operation yourself feels like conditioned response, and a computer feels like neither.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_celestial-sphere.png" alt="" role="presentation" loading="lazy"></div>

## Limits of Computer Applications—AI–III

The AI debate cannot be resolved by evidence because the key terms—thinking, learning, intelligence—are undefined and perhaps indefinable; what matters for your career is that you examine your own position critically, since false beliefs will exclude you from the computerization of your field, while uncritical belief will lead you into first-class failures.

* <span id="the-art-of-doing-science-and-engineering-learning--034"></span>**The most common objections to machine capabilities—'I wouldn't want my life to depend on a machine'; 'machines can never do what humans do'—collapse immediately when confronted with pacemakers, unstable-aircraft stabilizers, and ICU monitoring systems that already do exactly that.**
    - People who say they do not want their lives to depend on a machine conveniently forget pacemakers keep many people alive.
    - Often humans can cooperate with a machine far better than with other humans—yet people keep their feelings of supposed superiority rather than looking for places where machines can improve matters.
* <span id="the-art-of-doing-science-and-engineering-learning--035"></span>**The most productive AI framing is not 'can machines think?' but 'what future applications of computers in your domain have you not yet imagined?'—and people are consistently more inhibited imagining applications in their own field than in someone else's.**
    - Discussions of AI tend to report past and present applications rather than speculating about future ones, which is the actual purpose of sensitizing people to future possibilities.
    - People are sure of their supposed superiority over machines in some area and cling to it rather than finding where machines can actually help—the combination of human and machine is what matters, not the competition.
* <span id="the-art-of-doing-science-and-engineering-learning--036"></span>**The hard AI claim that molecule-banging-against-molecule is all there is leads to determinism and the denial of free will; no satisfactory experiment can settle the question, and the feeling of self-awareness and self-consciousness—though difficult to operationalize—is a datum that materialist physics cannot simply wave away.**
    - The claim that a truly random source contains all knowledge (via the infinite-monkeys argument) is logically inescapable but practically useless—waiting times are too long and recognizing information when you see it remains unsolved.
    - Dark matter constitutes 90–99% of the universe by current (1994) estimates, and physics knows nothing about it except its gravitational attraction—making claims of complete physical description premature.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_small-planet.png" alt="" role="presentation" loading="lazy"></div>

## n–Dimensional Space

Intuition built on two and three dimensions is systematically wrong in high-dimensional spaces—almost all volume lies near the surface, diagonal directions are nearly perpendicular to all coordinate axes, and a sphere packed inside a grid of corner-spheres eventually extends outside its containing cube—making a rigorous feel for n-dimensional geometry essential for anyone doing complex design or optimization.

* <span id="the-art-of-doing-science-and-engineering-learning--037"></span>**In n-dimensional space, almost all volume of a sphere lies in a thin shell near the surface, regardless of how thin you make the shell relative to the radius—which means optimal designs almost always lie on the boundary of feasible regions, not in the interior, making calculus-style interior optimization methods typically inappropriate.**
    - The relative volume of the shell at fractional thickness ε is 1 - (1-ε)^n, which approaches 1 for large n no matter how small ε is.
    - Even in three dimensions, 7/8 of a unit sphere's volume lies within 1/2 of the surface.
* <span id="the-art-of-doing-science-and-engineering-learning--038"></span>**The diagonal of an n-dimensional unit cube makes an angle with each coordinate axis whose cosine is 1/√n—nearly perpendicular for large n—and there are 2^n such nearly-perpendicular diagonals, making the geometry of high-dimensional spaces far richer and stranger than three-dimensional intuition suggests.**
    - By the weak law of large numbers, the dot product of two random ±1 vectors of length n divided by n approaches 0 almost surely—almost every pair of such vectors is nearly orthogonal.
    - In n=10 dimensions, an inner sphere touching all 1024 corner-packed unit spheres has radius √10 - 1 ≈ 2.16, exceeding the cube's half-width of 2 and thus extending outside the cube.
* <span id="the-art-of-doing-science-and-engineering-learning--039"></span>**Three different metrics—L2 (Euclidean/Pythagorean), L1 (Manhattan/Hamming distance), and L∞ (Chebyshev/maximum-coordinate)—all satisfy the four axioms of a metric and are appropriate for different domains: L2 for physical measurement, L1 and L∞ for intellectual judgments and pattern recognition.**
    - In real complex design problems, different coordinates may use different metrics, producing a messy hybrid space unlike the clean idealized spaces of textbook geometry.
    - The chi-squared test is an L2 measure and is widely misapplied in situations where L1 would be more appropriate.
* <span id="the-art-of-doing-science-and-engineering-learning--040"></span>**Real design occurs in high-dimensional spaces whose peculiarities—near-perpendicularity of most directions, surface-concentration of volume, counter-intuitive sphere packing—mean that engineers and scientists who have not internalized these properties will regularly misjudge the nature of optimization problems.**
    - You think you live in three dimensions, but in random walks you effectively live in two—fish reduce three-dimensional ocean to two dimensions by schooling or bottom-feeding, and truly random three-dimensional flight would have fewer airplane accidents.
    - The theory and practice of linear algebra are quite different: finding n orthogonal basis vectors leaves 2^n other directions that are almost perpendicular to those n vectors.


<div class="chapter-glyph"><img src="/glyphs/Education/Earth_figure-surveying.png" alt="" role="presentation" loading="lazy"></div>

## Coding Theory—I

Shannon's information theory provides a framework for representing information as symbol strings with probabilities, and the Kraft inequality and McMillan's theorem establish that instantaneous unique decodability costs nothing—setting the stage for optimal Huffman encoding and channel coding by showing that code design is equivalent to efficient packing in an abstract space.

* <span id="the-art-of-doing-science-and-engineering-learning--041"></span>**The standard model of information transmission—source, encoder, noisy channel, decoder, sink—provides a powerful abstraction by divorcing the theory from the meaning of symbols, making it applicable to telephone, radio, computer storage, and any other transmission medium.**
    - Shannon insisted on 'information theory' over the more accurate 'communication theory' for publicity reasons—a choice that created lasting confusion because the theory handles symbol strings, not human information.
    - Transmission through space and transmission through time (storage) are the same problem.
* <span id="the-art-of-doing-science-and-engineering-learning--042"></span>**A code is uniquely decodable if and only if it satisfies the Kraft inequality Σ2^(-li) ≤ 1, and McMillan's theorem shows that non-instantaneous unique decodability buys nothing—so the simpler instantaneous codes can always be used without loss.**
    - The proof of McMillan's theorem uses the fact that for K > 1, some nth power of K exceeds any linear function of n—so if K > 1 the Kraft sum to the nth power eventually contradicts unique decodability.
    - Comma codes (strings of 1s followed by a 0, except the last symbol) exactly meet the Kraft inequality with equality.
* <span id="the-art-of-doing-science-and-engineering-learning--043"></span>**Human communication of ideas differs fundamentally from the formal model: the 'meaning' is not contained in the specific words but is reconstructed by the receiver from surrounding context—meaning transmission from sender to receiver is inherently lossy and context-dependent in ways the formal theory does not capture.**
    - When you later retransmit an idea to a friend, you will almost certainly use different words—showing the same information can be encoded many ways and meaning is not in the words themselves.
    - In organizations, lower management often hears only what they expect to hear from senior management—a serious problem as you rise toward leadership.


<div class="chapter-glyph"><img src="/glyphs/Education/Life_person-brain-thinking.png" alt="" role="presentation" loading="lazy"></div>

## Coding Theory—II

Huffman coding achieves the minimum average code length for a given probability distribution by iteratively merging the two least-probable symbols, and the payoff is large when symbol probabilities are very unequal; the chapter also introduces weighted parity codes designed for human error patterns—transpositions and doublings—which catch both single-symbol changes and adjacent-symbol interchanges.

* <span id="the-art-of-doing-science-and-engineering-learning--044"></span>**Huffman's algorithm achieves minimum average code length by proving two necessary conditions—probabilities and code lengths must be in opposing order, and two longest symbols must have the same length—and then constructing the optimal code by iteratively merging the two least probable symbols.**
    - Huffman encoding can save more than half of expected storage space; it is easily automated—the machine samples data, estimates probabilities, finds the Huffman code, sends the decoding tree, and then the encoded data, all without human intervention.
    - The code is not unique: at each split it is arbitrary which symbol gets 0 and which gets 1, and equal probabilities can be ordered either way—but all variants achieve the same average length L.
* <span id="the-art-of-doing-science-and-engineering-learning--045"></span>**Huffman coding pays off substantially when symbol probabilities are very unequal (approaching a comma code) and hardly at all when probabilities are nearly equal—the variance of code length can be minimized by always inserting new combined probabilities as high as possible in the ordering.**
    - Rule: Huffman coding pays off when the probabilities of the symbols are very different, and does not pay off much when they are all rather equal.
    - Huffman codes have been used for the instruction part of computer instructions, since different instructions have very different probabilities of being used.
* <span id="the-art-of-doing-science-and-engineering-learning--046"></span>**Standard parity checks detect odd numbers of errors but fail against human error patterns; Ed Gilbert's weighted modular code—assigning values 0–36 to symbols and computing a weighted sum modulo 37—catches both single-symbol changes and adjacent-symbol transpositions, because 37 is prime.**
    - Human error data from telephone dialing shows strong tendency to interchange adjacent digits (67→76) and double a digit (556→566)—patterns that single parity checks miss.
    - The ISBN system uses the same weighted-code principle with ten decimal digits plus X as an 11th symbol (ten not being prime), catching most single errors.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_star-detailed.png" alt="" role="presentation" loading="lazy"></div>

## Error-Correcting Codes

Hamming error-correcting codes arose from emotional frustration with relay computer failures and were discovered by recognizing that parity-check syndromes could directly encode the binary position of an error—and the deeper geometric insight that finding an error-correcting code is equivalent to packing non-overlapping spheres in n-dimensional L1 space shows why the codes work and how powerful 'prepared mind' plus luck can be.

* <span id="the-art-of-doing-science-and-engineering-learning--047"></span>**Error-correcting codes were discovered when Hamming, furious that a relay machine had wasted two weekends by detecting but not locating errors, asked: 'If the machine can locate there is an error, why can it not locate where it is?'—illustrating that great discoveries typically require emotional stress, not calm detachment.**
    - The discovery required the immediately prior preparation of having understood 2-out-of-5 codes fundamentally and having worked out the general implications of parity checks.
    - Working calmly will let you elaborate and extend things, but breakthroughs generally come only after great frustration and emotional involvement.
* <span id="the-art-of-doing-science-and-engineering-learning--048"></span>**The Hamming code design follows directly from using the syndrome—the pattern of failing parity checks—as a binary number naming the error position: parity check k covers all positions whose binary representation has a 1 in bit position k, making the syndrome exactly the binary address of any single error.**
    - The condition 2^r ≥ n + 1 (where r is the number of check bits and n is the total message length) is both necessary and sufficient for single-error correction.
    - Adding one overall parity check converts a single-error-correcting code to a single-error-correcting, double-error-detecting code at minimal cost.
* <span id="the-art-of-doing-science-and-engineering-learning--049"></span>**Error-correcting codes are geometrically equivalent to packing non-overlapping spheres in n-dimensional L1 space—minimum distance between code points determines correctability—which is the same metric Hamming had just analyzed abstractly, illustrating why cross-disciplinary knowledge pays dividends.**
    - The minimum-distance table: distance 1 = unique decoding; 3 = single error correcting; 5 = double error correcting; 2k+1 = k error correcting.
    - At the first electronic central office installation using Hamming codes in Morris, Illinois (1961), the field installation went in more easily than any other—self-checking properties meant any newly functioning unit stayed trustworthy while the engineer moved on to the next.
* <span id="the-art-of-doing-science-and-engineering-learning--050"></span>**The practical lesson of the discovery is that being in the same situation as Hamming was not sufficient for others to make the same discovery—the difference was systematic preparation through deep understanding of prior work, not raw intelligence, and this means you, adequately prepared, could have done it too.**
    - Many people were in much the same situation but did not make the discovery—luck played a role, but preparation was the decisive differentiator.
    - What it takes to be great in one age is not what is required in the next—hence preparing for future greatness requires imagination about the nature of that future.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_rocket-ship.png" alt="" role="presentation" loading="lazy"></div>

## Information Theory

Shannon's information theory measures surprise with -log2(p) and proves the noiseless coding theorem (entropy is a lower bound on average code length) and the noisy coding theorem (reliable communication at rates up to channel capacity C is possible for large n), but the theory should have been called 'communication theory' because it measures statistical surprise, not human information—and all definitions, including Shannon's, should be inspected for how they distort the concepts they formalize.

* <span id="the-art-of-doing-science-and-engineering-learning--051"></span>**Shannon defined information as surprise—I(p) = -log2(p)—the unique continuous, additive measure of probability; entropy H = -Σ pi log2(pi) is the average information and equals log2(q) at maximum when all q symbols are equally probable, by Gibbs' inequality.**
    - Shannon chose 'information theory' over Bell Labs management's preference for 'communication theory' for publicity reasons—creating lasting confusion because the theory handles symbol surprise, not human meaning.
    - The measure is relative: the same symbol string contains no information if you know the generating formula, and maximum information if you think the source is random.
* <span id="the-art-of-doing-science-and-engineering-learning--052"></span>**Shannon's noisy coding theorem proves that for the binary symmetric channel, there exists a code achieving arbitrarily low error probability at any rate below channel capacity C = 1 - H(Q)—but the proof is non-constructive, using random coding averaged over all code books, so 'sufficiently large n' is astronomically large in practice.**
    - The decisive step is averaging the error probability over all random code books: if the average is small, at least one code must be good—existence without construction.
    - Satellite missions to the outer planets confirmed the theorem's relevance by using codes correcting hundreds of errors per block transmitted with only 5–20 watts across billions of kilometers.
* <span id="the-art-of-doing-science-and-engineering-learning--053"></span>**Every definition—including Shannon's definition of information, and IQ—should be examined for how it distorts the original intuitive concept, because in the long run it is the formal definition that determines meaning, not the original intuition, and this distortion is greatest in the softer sciences.**
    - Eddington's fishermen concluded there is a minimum fish size from examining only what their net could catch—the tool used, not reality, determined the conclusion.
    - IQ is defined circularly: a test is revised for internal consistency, calibrated to produce a normal distribution, and then declared to measure 'intelligence'—so of course intelligence is normally distributed.


<div class="chapter-glyph"><img src="/glyphs/Education/Life_people-connected.png" alt="" role="presentation" loading="lazy"></div>

## Digital Filters—I

Digital filters arise necessarily from three convergent reasons—time-invariance, linearity, and Nyquist's sampling theorem all point to complex exponentials as eigenfunctions—and the transfer function is simply the eigenvalue of the filter at each frequency, a unifying insight that most electrical engineers who use the concept have never recognized.

* <span id="the-art-of-doing-science-and-engineering-learning--054"></span>**The exclusive use of Fourier/trigonometric functions in signal processing is not arbitrary but follows from three independent reasons: (1) time-invariance requires the eigenfunctions of translation, (2) linearity has the same eigenfunctions, and (3) the Nyquist sampling theorem shows that band-limited signals sampled at ≥2× the highest frequency can be perfectly reconstructed from equally spaced samples.**
    - When Hamming asked various electrical engineers why sinusoids dominated the field, no one could give a satisfying answer—one said 'alternating currents are sinusoidal,' which Hamming found meaningless.
    - The 'transfer function' is exactly the eigenvalue of the filter at each frequency—a connection that apparently no electrical engineer had pointed out to Hamming, despite both concepts appearing in their curricula.
* <span id="the-art-of-doing-science-and-engineering-learning--055"></span>**Aliasing—the folding of frequencies above the Nyquist rate into lower frequencies—is the fundamental effect of sampling, and thinking of it as permanent (once sampled, the aliased signal is what you have) saves enormous conceptual effort compared to drawing periodic extensions.**
    - A single high frequency aliases into a single low frequency under uniform sampling—true only for trigonometric functions, not for powers of t or other function sets.
    - Stretching time to normalize the sampling rate to one per unit removes extraneous scale factors and allows insights from different physical timescales to cross-fertilize.
* <span id="the-art-of-doing-science-and-engineering-learning--056"></span>**Smoothing filters derived from least-squares polynomial fitting (linear, quadratic) produce the central-value estimate as a weighted running average of nearby data, with the filter 'shape' (coefficient window) determining which frequencies are passed and which are attenuated.**
    - For a least-squares linear fit to five points, the smoothed value is simply the average of the five—a uniform window.
    - The quadratic smoothing case produces coefficients with negative values, which should not trouble us since 'window' is metaphorical and negative transmission is mathematically legitimate.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_saturn-planet.png" alt="" role="presentation" loading="lazy"></div>

## Digital Filters—II

The Gibbs phenomenon—an ~9% overshoot at discontinuities that does not diminish with more Fourier terms—is the central obstacle in nonrecursive filter design, and windows (Lanczos sigma factors, von Hann raised cosine, Hamming raised cosine on a platform) reduce but do not eliminate it by trading frequency-domain leakage against overshoot.

* <span id="the-art-of-doing-science-and-engineering-learning--057"></span>**The Gibbs phenomenon—an overshoot of approximately 8.949% at any discontinuity in a truncated Fourier series that persists regardless of how many terms are taken—was correctly identified by Gibbs after the phenomenon's discoverer Michelson was told by 'experts' his precision equipment must be faulty.**
    - Cauchy's textbooks in the 1850s simultaneously stated that a convergent series of continuous functions converges to a continuous function AND demonstrated the Fourier expansion of a discontinuous function—a flat contradiction that implied the need for uniform convergence.
    - For general orthogonal functions the overshoot magnitude depends on where the discontinuity occurs; for Fourier functions it is location-independent.
* <span id="the-art-of-doing-science-and-engineering-learning--058"></span>**A filter is the convolution of one array of coefficients by another—equivalently, multiplication of corresponding Fourier functions—and a finite observation window (a rectangular window) convolves the true spectrum with a (sin x)/x function, smearing spectral lines and introducing the Gibbs phenomenon.**
    - Whether you sample-then-truncate or truncate-then-sample gives the same result—the order of operations does not matter for equally spaced sampling and finite-range observation.
    - The Lanczos modification—changing only the two outer coefficients from 1 to 1/2—reduces the overshoot by a factor of ~7 at minimal cost, because the mid-value at a jump should be 1/2, not 1.
* <span id="the-art-of-doing-science-and-engineering-learning--059"></span>**The Hamming window—a raised cosine on a platform with weights 0.54 and 0.46—was designed to minimize the maximum side lobe rather than minimize total leakage, and is named by Tukey, who called it 'hamming' to make Hamming famous in the way that watt and volt became common words.**
    - The von Hann window is preferable in most situations; the Hamming window is specifically suited to spectra with a single strong line that must be kept from leaking into adjacent frequency estimates.
    - It pays to be helpful to others as they try to do their work—they may in time give you credit, which is better than trying to claim it yourself.


<div class="chapter-glyph"><img src="/glyphs/Education/Life_person-magnifying.png" alt="" role="presentation" loading="lazy"></div>

## Digital Filters—III

Kaiser's systematic design method for nonrecursive filters derives both the number of coefficients N and the window shape from user-specified passband ripple δ and transition width ΔF, using the I₀(x) Bessel function window discovered partly by computer experimentation—illustrating the general design process and the power of using the computer as an experimental tool even in theoretical research.

* <span id="the-art-of-doing-science-and-engineering-learning--060"></span>**The systematic design of nonrecursive digital filters proceeds in six steps: sketch the ideal transfer function, compute Fourier coefficients, truncate (rectangular window), apply a smoothing window to reduce Gibbs overshoot, evaluate the windowed transfer function, and round coefficients before final evaluation.**
    - Kaiser's method specifies only δ (vertical tolerance from ideal) and ΔF (transition width) and returns both N and the Kaiser I₀(αr/r₀) window—eliminating the trial-and-error of choosing both N and window type separately.
    - Kaiser found the exponent 0.4 by trying 0.5 (too large) and then 0.4, which fit well—a good example of using the computer as an experimental tool in theoretical research.
* <span id="the-art-of-doing-science-and-engineering-learning--061"></span>**The fast Fourier transform (FFT) reduces the N² operations of a direct DFT to N log N by (1) adding/subtracting before multiplying and (2) computing higher frequencies by multiplying lower ones—but Hamming failed to implement it because he remembered only that it was impractical on his old equipment, not why, illustrating a critical error to avoid.**
    - A book Hamming published in 1961 shows he knew all the facts necessary to derive the FFT, yet he dismissed it as one of Tukey's few bad ideas—because he forgot the essential reason was the hardware of the time, not the idea itself.
    - Moral: when you decide something is impossible, record the specific reason why; later, when circumstances change, you must re-examine whether the original reason still applies.
* <span id="the-art-of-doing-science-and-engineering-learning--062"></span>**Power spectrum analysis forces all non-harmonic frequencies into harmonic ones (making the function periodic over the sample window) and all non-integer harmonics distribute their energy across many frequency bins—a consequence of the FFT's implicit periodicity assumption that is widely misunderstood.**
    - The old Fourier analysis of stock market data showed only white noise and was interpreted as proving no prediction is possible—but this conclusion is valid only for linear predictors; it says nothing about nonlinear ones.
    - Linear time invariance leads automatically to Fourier eigenfunctions, which have an uncertainty principle—so the famous Heisenberg uncertainty principle may be an artifact of the assumed linearity of quantum mechanics, not a fact about nature.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_satellite-orbit.png" alt="" role="presentation" loading="lazy"></div>

## Digital Filters—IV

Recursive (IIR) filters introduce feedback and therefore stability questions, are equivalent to solving difference equations with constant coefficients, and arise naturally in numerical integration of differential equations—where Hamming's experience showed that 'stability' should mean 'not exponential growth' (allowing polynomial growth for integration) rather than the classical analog filter definition of 'bounded output.'

* <span id="the-art-of-doing-science-and-engineering-learning--063"></span>**Recursive digital filters—output depends on both input and previous output—are simply difference equations with constant coefficients, and their transfer function is a rational function in z = e^iωt rather than a polynomial, making systematic design harder and requiring case-by-case methods (Butterworth, Chebyshev, elliptic).**
    - The corrector in a predictor-corrector numerical integrator is exactly a recursive digital filter where the 'input' is derivatives from the differential equation and the 'output' is position—showing that numerical integration IS recursive digital filtering.
    - For two-sided processing (non-real-time), data recorded on tape gives access to future values, making two-sided recursive filters possible and potentially much more accurate.
* <span id="the-art-of-doing-science-and-engineering-learning--064"></span>**Stability in digital filters—the claim that all IIR filters have infinite impulse response—is a convention inherited from analog filter theory, not a necessity; Hamming found a counterexample and used it to illustrate that experts often repeat claims learned as students without ever examining whether they remain true in all circumstances.**
    - The instability of a hot-water shower with a long pipe delay is an everyday example of feedback instability: too-strong response to delayed signal causes hunting—which can be viewed as either too-large gain or too-large detection delay.
    - Stability here should mean 'not exponential growth' and should allow polynomial growth—integration of a constant produces linear growth, which is what must happen.
* <span id="the-art-of-doing-science-and-engineering-learning--065"></span>**Digital filters for non-time-domain signals—such as differentiating nuclear count spectra as a function of energy—require the filter designer to free themselves from time-signal assumptions, and the most important contribution is often identifying the problem, finding the right collaborators, and keeping experts on track.**
    - Kaiser, one of the world's experts in digital filters, could not solve the problem until Hamming bluntly said 'his energy is time and the measurements are the voltage'—the curse of the expert limiting their view.
    - Working in the square roots of counts rather than counts themselves, because counts have unequal variances, was the final statistical refinement the physicist needed to be reminded of.


<div class="chapter-glyph"><img src="/glyphs/Science/Earth_flood-destruction.png" alt="" role="presentation" loading="lazy"></div>

## Simulation—I

Simulation answers 'what if?' questions that experiments cannot, and the major lessons from Hamming's early simulations—atomic bomb, Nike missiles, travelling wave tubes—are: (1) start simple to gain insight before elaborating, (2) require domain experts to be deeply involved in every coding detail, and (3) use the simulation actively to discover physics the proposers had not thought about.

* <span id="the-art-of-doing-science-and-engineering-learning--066"></span>**Computers have largely replaced laboratory experiments (9 out of 10 experiments now on machines) because simulation is cheaper, faster, more flexible, and can do what no laboratory can—but this trend risks a return to scholasticism, where models are trusted over direct observation of nature.**
    - Simulation is defined as the answer to the question 'What if...?'—making it essential for any organization that must make decisions about futures it cannot directly test.
    - Intellectual shelf life—the decay of skills needed to run laboratory equipment—is often more insidious than physical shelf life of the equipment.
* <span id="the-art-of-doing-science-and-engineering-learning--067"></span>**Domain-expert involvement in every programming detail is essential because both the expert and the programmer can know exactly what the mathematical symbols mean yet disagree on the correct interpretation—as happened with 'fin limiting' vs. 'voltage limiting' in a Navy intercept simulation.**
    - Hamming refused to code any simulation until the domain expert sat with him and walked through each line of absolute binary code, understanding what was happening at each step.
    - Expert knowledge of the field is needed to know whether effects omitted from the model are vital or safely ignored—only an expert can make that judgment.
* <span id="the-art-of-doing-science-and-engineering-learning--068"></span>**Starting with a simple simulation and evolving to a detailed one yields the critical early insights that would be disguised in a full-scale model—Hamming's Nike missile simulations showed vertical launch was universally superior and that larger wings actually reduced end-game maneuverability, insights that shaped the entire design.**
    - Having lots of time to observe slowly-running simulations on the RDA #2 differential analyzer gave Hamming time to develop a 'feel' for the missile's behavior—he doubts hundreds of fast solutions would have taught as much.
    - Jargon functions simultaneously as a useful restricted language and as a barrier that blocks outsider contributions; consciously resisting jargon when outsiders are present is essential because modern work requires larger-than-tribal collaboration.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_star-circle-cosmos.png" alt="" role="presentation" loading="lazy"></div>

## Simulation—II

The fundamental question for any simulation—'Why should anyone believe it is relevant?'—has no silver bullet answer; reliability requires checking both modeling accuracy and computational accuracy, guarding against the Hawthorne-like tendency to find what you want to find, and recognizing that many simulations are essentially Rorschach tests dressed up as quantitative analysis.

* <span id="the-art-of-doing-science-and-engineering-learning--069"></span>**Simulation reliability requires separately evaluating both the accuracy of the model (are the right equations being solved?) and the accuracy of the computation (are they being solved correctly?)—and when asked about reliability, practitioners almost always respond with irrelevant information about manpower, computer size, and problem importance.**
    - A spaceflight simulation reliability expert was forced to admit under questioning that his '99.44% reliability' figure described the simulation, not the actual flight—and that the program director did not understand this distinction.
    - The Club of Rome world simulation had equations that guaranteed catastrophe regardless of initial conditions or parameter choices, and was later found to have serious computational errors as well.
* <span id="the-art-of-doing-science-and-engineering-learning--070"></span>**Many simulations are Rorschach tests—the analyst finds what they want to find—and medicine had to invent the double-blind experiment precisely because even honest doctors could not avoid seeing improvement where they expected it; simulation practitioners are no more immune to self-delusion than physicians.**
    - A Bell Labs psychologist showed that not one scientist among many tested—all running random-light experiments—ever concluded there was no message; only statisticians and information theorists trained to recognize randomness would have.
    - Iterating between assumed model structure and observed behavior until they agree (as Forrester describes) is indistinguishable from adjusting the model to get the desired result.
* <span id="the-art-of-doing-science-and-engineering-learning--071"></span>**Simpson's paradox illustrates that combining data can create apparent effects not present in any subgroup—the UC Berkeley graduate admissions data showed apparent sex discrimination in aggregate while no department discriminated—warning that amalgamated data must be handled with extreme care.**
    - The explanation: departments with many openings (hard sciences) attracted more men, while departments with few openings (humanities, social sciences) attracted more women—the discrimination, if any, was in earlier educational tracking.
    - The scenario method—giving multiple possible projections rather than a single prediction—is the best available approach for systems where humans can alter their behavior in response to the simulation's outputs.


<div class="chapter-glyph"><img src="/glyphs/Science/Earth_gears-machinery.png" alt="" role="presentation" loading="lazy"></div>

## Simulation—III

'Garbage in, garbage out' is not always true—feedback in the problem can compensate for inaccurate input data, as in H.S. Black's feedback amplifier insight and the atomic bomb equation-of-state computation—but the corollary that 'good data guarantees good output' is also false when the direction field is divergent, and these insights impact design: good design protects against needing too many highly accurate components.

* <span id="the-art-of-doing-science-and-engineering-learning--072"></span>**GIGO (garbage in, garbage out) is wrong in both directions: feedback can compensate for inaccurate input data (as in the Nike missile accident simulation where unknown initial conditions still gave a correct answer because of a strongly convergent direction field), and accurate input can still produce meaningless output when the direction field is divergent.**
    - The Nike 'telephone pole' missile breakups were solved using guessed initial conditions—the convergent guidance-feedback direction field meant errors in starting conditions automatically diminished.
    - The atomic bomb equation-of-state was drawn from scattered data using French curves and read to only 3⅓ significant figures, yet the predictions were accurate because the second-difference computation averaged over the history of each shell.
* <span id="the-art-of-doing-science-and-engineering-learning--073"></span>**Good design inherently protects against needing too many highly accurate components by building in feedback—just as Black's amplifier makes only one resistor critical while all other components can be inaccurate—but this principle is still poorly understood and not yet systematically incorporated into engineering design methods.**
    - H.S. Black's feedback amplifier equation shows output ≈ −(1/feedback resistance) when gain is very high—only the feedback element needs to be accurate.
    - Whether inaccurate numbers travel through a feedback-protected path or are 'vital' and unprotected must be understood for the whole computation as a whole.
* <span id="the-art-of-doing-science-and-engineering-learning--074"></span>**For simulations of inherently unstable differential equations (such as sinh y boundary value problems), the instability itself can be exploited as the solution method: tracking when the solution veers one direction tells you your slope estimate was too high or too low, enabling piece-by-piece navigation of the unstable solution curve.**
    - Pride in being able to deliver answers to important properly-posed problems—refusing to give up with excuses—was essential to finding the solution that apparently could not be found.
    - The frequency-domain approach to numerical ODE integration (aligning frequencies) differs fundamentally from the polynomial approach (aligning positions), and the pilot-training application shows the frequency approach better replicates the 'feel' of a vehicle.


<div class="chapter-glyph"><img src="/glyphs/Education/Life_person-brain-thinking.png" alt="" role="presentation" loading="lazy"></div>

## Fiber Optics

Hamming's approach to fiber optics—attending a seminar, identifying the key questions (splicing, bandwidth advantage over copper, duct capacity, signal security, EMI immunity), tracking which of the competing solutions would likely be solved, and staying prepared without becoming an expert—illustrates how a thoughtful generalist can remain useful at the frontier of a new technology without abandoning their primary expertise.

* <span id="the-art-of-doing-science-and-engineering-learning--075"></span>**Optical fiber was clearly destined to replace copper wire in the telephone network for at least three reasons: optical frequencies provide enormously greater bandwidth, glass is made from abundant sand while good copper is increasingly scarce, and Manhattan duct capacity was running out—making the development essential, not optional.**
    - The speaker's remark 'God loved sand, He made so much of it' triggered Hamming's recognition that raw material supply would favor glass over copper in the long run.
    - Fiber optics also proved resistant to electromagnetic disturbances including nuclear EMP and lightning, guaranteeing strong military support for the research.
* <span id="the-art-of-doing-science-and-engineering-learning--076"></span>**The graded-index fiber—with a smoothly changing refractive index rather than a sharp core/cladding boundary—is the optical analog of 'strong focusing' developed for cyclotrons, illustrating how recognizing an analogy across domains provides immediate insight into a new technology.**
    - Smaller fiber diameters allow sharper bends without light leaking out, hence the drive to hair-sized fibers is driven by flexibility requirements, not material cost.
    - The large number of competing splicing methods told Hamming that the splicing problem—his initial concern—would probably be solved, even if no single method dominated.
* <span id="the-art-of-doing-science-and-engineering-learning--077"></span>**Soliton signaling—where pulses maintain shape during propagation and can be amplified without reshaping—represents a potential paradigm shift from classical pulse signaling, and the satellite communication business faces fundamental limits (equatorial parking slots, signal spreading) that fiber optics does not.**
    - The inefficiency of detecting optical signals, converting to electronic form, amplifying, and converting back made optical amplifiers a predictable necessity—Hamming saw this as obviously bad system design.
    - Drop lines to houses carrying fiber would make all information channels (phone, radio, TV, personalized newspapers) selectable by setting digital filter parameters—changing 'channel' becomes a software operation.


<div class="chapter-glyph"><img src="/glyphs/Science/Life_moon-crescent.png" alt="" role="presentation" loading="lazy"></div>

## Computer-Aided Instruction (CAI)

The long history of failed easy-learning promises—from sleep learning to programmed textbooks to PLATO—should make us deeply skeptical of CAI claims, especially given the Hawthorne effect (any novel method improves results temporarily regardless of merit); computers genuinely help for low-level conditioned-response training but the jury is still out for high-level education, where we do not even know what 'educated' means for 2020.

* <span id="the-art-of-doing-science-and-engineering-learning--078"></span>**The Hawthorne effect—productivity rises whenever workers perceive change as being made for their benefit, regardless of whether the change is actually beneficial—vitiates almost all educational experimentation, because showing students a new method reliably improves outcomes whether the method is better or worse.**
    - At the Hawthorne plant, even reversing a change back to the original state caused productivity to rise—demonstrating that perceived care, not content, drove the improvement.
    - The proper teaching method may always be in a state of experimental change, since the Hawthorne effect ensures improvement regardless of what the change is.
* <span id="the-art-of-doing-science-and-engineering-learning--079"></span>**Computers genuinely improve training for conditioned responses—rote arithmetic, pilot emergency procedures—because these require reliable repetition that machines do better than teachers; but for high-level education involving abstract pattern recognition and transfer of training, computers have not demonstrated superiority.**
    - The weightlifting analogy: giving students easier proofs is like cutting the weights in half—and the evidence that famous professors who were terrible lecturers produced great students suggests difficulty in learning may be part of what builds intellectual strength.
    - Analytic integration in the calculus forces students to recognize forms independent of representation—abstract pattern recognition essential to mathematics—and should not be automated away unless replaced by something of equivalent difficulty.
* <span id="the-art-of-doing-science-and-engineering-learning--080"></span>**The failure to transfer learning between contexts—students who knew ∫(1/x)dx in calculus class couldn't recognize it as ln x in a thermodynamics class across the hall—is a deep problem that better graphics and more elaborate CAI may actually worsen by binding concepts more strongly to specific visual representations.**
    - Kaiser, an expert in digital filters, could not apply his knowledge when the independent variable was energy rather than time—his expertise had restricted his view.
    - The better we inculcate a basic idea with the professor's specific pictures, the more we prevent students from later extending it to completely new areas the professor never imagined.


<div class="chapter-glyph"><img src="/glyphs/Science/Life_grapes-cluster.png" alt="" role="presentation" loading="lazy"></div>

## Mathematics

Mathematics has no satisfactory definition—the five major schools (Platonic, formalist, logicist, intuitionist, constructivist) all fail—but its 'unreasonable effectiveness' arises from recognizing analogies between formal structures and pieces of reality, and since no definition perfectly matches intuition, all definitions should be inspected for the distortions they introduce.

* <span id="the-art-of-doing-science-and-engineering-learning--081"></span>**The five schools of mathematical philosophy—Platonism (mathematical objects exist independently), formalism (mathematics is a meaningless symbol game), logicism (mathematics is a branch of logic), intuitionism (rigor is relative), and constructivism (only explicitly constructed objects exist)—all fail to fully account for both mathematics' internal structure and its practical effectiveness.**
    - Hilbert added many postulates to Euclid to handle betweenness and intersection—yet no theorem in Euclid's 467-theorem corpus turned out to be false, suggesting Euclid worked backward from known results to the postulates needed, not forward from axioms to conclusions.
    - Most mathematicians are Platonists while working but take refuge in formalism when pressed—pretending to believe mathematics has no meaning while actually finding it enormously meaningful.
* <span id="the-art-of-doing-science-and-engineering-learning--082"></span>**The 'unreasonable effectiveness of mathematics' arises not from mathematics being true or meaningful in itself, but from recognizing analogies between formal structures and parts of reality—and meaning is placed into symbols by humans when converting problems to mathematics and when interpreting results, not by the symbols themselves.**
    - The meaning of an instruction in an interpretive language comes from the subroutine it calls, not from its name—exactly as mathematical symbols get meaning from how they are processed, not from their definitions.
    - Einstein observed that the world appears logically constructed—that it can be understood mathematically—which Hamming regards as the most amazing fact about reality.
* <span id="the-art-of-doing-science-and-engineering-learning--083"></span>**Gödel's theorem shows that any sufficiently rich discrete symbol system contains statements whose truth cannot be proved within the system—but natural language as actually used escapes Gödel's hypotheses because words have multiple context-dependent meanings, which may be why language evolved with this property.**
    - Music, poetry, and the classical Greek ideals of truth, beauty, and justice apparently cannot be fully captured in words—suggesting there are things that cannot be communicated in any discrete symbol system.
    - Since past mathematics found the easy applications first, the future will require new mathematics for harder problems—including things where the whole is not the sum of the parts.


<div class="chapter-glyph"><img src="/glyphs/Science/Life_microscope-lens.png" alt="" role="presentation" loading="lazy"></div>

## Quantum Mechanics

Quantum mechanics has been spectacularly successful as a formal mathematical structure despite nobody being able to 'understand' it in the classical sense—the wave-particle duality remains unexplained after 70 years, the Aspect experiments demonstrate non-local effects that violate common intuition, and this pattern of successful-but-incomprehensible formalism is likely to recur as future science probes deeper into nature.

* <span id="the-art-of-doing-science-and-engineering-learning--084"></span>**Planck discovered the quantum by accident—he used a mathematical trick of discretizing energy to derive a formula that fit black-body radiation data, then found the fit disappeared when he took the limit to continuity, and was honest enough to stop before the limit.**
    - Hamming adopted the lesson of fitting problems with functions the client already believes in, rather than standard polynomials—hoping to produce Planck-like insights rather than mere numerical answers.
    - Two apparently different theories—Heisenberg's matrix mechanics and Schrödinger's wave mechanics—were shown to be equivalent, demonstrating that there need not be a unique theoretical form to account for a body of observations.
* <span id="the-art-of-doing-science-and-engineering-learning--085"></span>**The Heisenberg uncertainty principle for conjugate variables is a theorem in Fourier transforms—any linear theory must have a corresponding uncertainty principle—suggesting the famous QM uncertainty principle may be an artifact of the assumed linearity of the model rather than a physical fact about nature.**
    - Von Neumann 'proved' there are no hidden variables, but the proof was later found fallacious; new proofs found, then found fallacious again—the question remains open.
    - The probabilistic basis of QM attracted philosophers to debates about free will, but Hamming doubts there is any real connection between QM randomness and human agency.
* <span id="the-art-of-doing-science-and-engineering-learning--086"></span>**Alain Aspect's experiments demonstrate non-local effects—measuring the polarization of one particle of an entangled pair instantaneously affects the other, regardless of distance—and while this apparently does not allow faster-than-light signaling, it forces acceptance of non-locality that Einstein refused to accept.**
    - The Einstein-Podolsky-Rosen paper identified the constraints that non-local effects would impose; Bell sharpened these into testable 'Bell inequalities' that experiments have now consistently violated.
    - After almost 70 years of QM, professors are still forced to say 'I cannot explain wave-particle duality—you will just have to get used to it,' suggesting there may be thoughts the human brain as currently wired simply cannot think.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_saturn-planet.png" alt="" role="presentation" loading="lazy"></div>

## Creativity

Creativity follows a recognizable pattern—problem recognition, emotional engagement, gestation, sudden insight from the subconscious—and while it cannot be taught by tricks, it can be cultivated by saturating the subconscious with a problem, building many retrieval 'hooks' through multi-angle examination of new knowledge, and deliberately changing oneself toward more creative habits, starting with small changes and building toward larger ones.

* <span id="the-art-of-doing-science-and-engineering-learning--087"></span>**Creativity typically requires emotional involvement and often frustration—working calmly on a problem rarely produces breakthroughs; great creative acts generally follow periods of stress, intense engagement, and temporary abandonment of the problem to let the subconscious work.**
    - The pattern: dim recognition of the problem → refinement (don't rush, or you'll find only the conventional solution) → intense gestation → insight from the subconscious → often wrong, then back to drawing board → eventual solution.
    - When stuck, asking 'If I had a solution, what would it look like?' sharpens the approach and may reveal ways of looking at the problem that were subconsciously ignored.
* <span id="the-art-of-doing-science-and-engineering-learning--088"></span>**Analogy is the most important tool in creativity—and wide acquaintance with many fields, with knowledge 'filed' under multiple hooks for flexible retrieval, makes useful analogies more likely; Tukey recalled relevant information far more often than Hamming because Tukey had more retrieval hooks from mulling new ideas over repeatedly.**
    - A valuable analogy need not be close—it only needs to suggest what to do next; Kekule's snake-biting-its-own-tail dream suggested the ring structure of carbon compounds from a highly imperfect analogy.
    - When learning something new, think of other applications it might have in situations not yet encountered—this builds the hooks that make later retrieval possible.
* <span id="the-art-of-doing-science-and-engineering-learning--089"></span>**Creativity can be cultivated by deliberately changing your habits—starting with small self-modifications and building capacity for larger ones—because we are in a very real sense the sum total of our habits, and habits can be changed; but overconfidence leads to the Einstein trap of spending decades on a problem that never yields.**
    - Einstein spent the second half of his career on a unified field theory and produced almost nothing, while his early work—prepared by asking as a 12-year-old what light looks like at the speed of light—was transformative.
    - Hamming regularly made himself promises to deliver a result by a given date, then like a cornered rat had to find something—a form of self-management that repeatedly produced results.


<div class="chapter-glyph"><img src="/glyphs/Technology & Engineering/Life_tower-antenna.png" alt="" role="presentation" loading="lazy"></div>

## Experts

Experts block progress by applying past solutions to new situations without examining whether the underlying assumptions still hold—and most great innovations come from outside fields (carbon dating in archaeology, automatic telephone exchange from an undertaker, continental drift from children's observations)—making both the management of experts and the prevention of becoming a blocking expert central challenges for technical leaders.

* <span id="the-art-of-doing-science-and-engineering-learning--090"></span>**Kuhn's paradigm framework—normal science elaborates an accepted framework while ignoring contradictions until a sudden paradigm shift overturns the old—describes not just major scientific revolutions but also smaller-scale expert resistance to innovations in methods, tools, and approaches.**
    - Continental drift was discussed by Thomas Dick in 1838, published by Wegener in the early 1900s (with matching rock sequences on facing coasts as evidence), and rejected by geologists for decades—only oceanographic mapping of sea-floor spreading after WWII produced acceptance.
    - Most great innovations come from outside the field: carbon dating from physics into archaeology, automatic telephone exchange from an undertaker, Einstein working in a patent office when academic physics had no room for him.
* <span id="the-art-of-doing-science-and-engineering-learning--091"></span>**All impossibility claims rest on assumptions that may not apply to the new situation—experts rarely inspect these assumptions before declaring something impossible, and the patent office's rejection of a pump that lifted water more than 33 feet was based on this error.**
    - The man demonstrated his device by pumping water to the roof of the patent office building—far more than 33 feet—using standing waves, a method the textbook rule had never considered.
    - Experts forget the essential reason why they earlier concluded something was impossible; when circumstances change, the old reasoning no longer applies but the conclusion persists.
* <span id="the-art-of-doing-science-and-engineering-learning--092"></span>**When you rise to the top and are the expert, the methods that made you successful are likely to be counterproductive—the direction of progress has turned nearly perpendicular to the direction you mastered—and the most important thing you can do for the next generation is to get out of their way.**
    - Hamming refused to participate in any decisions about current computer choices after retiring, specifically to avoid being the drag on the next generation that he had to endure from his predecessors.
    - Einstein, who gave quantum mechanics such a start with his photoelectric paper, became a plain drag on QM as it developed—yet physicists are reluctant to admit this.


<div class="chapter-glyph"><img src="/glyphs/Science/Earth_circle-void.png" alt="" role="presentation" loading="lazy"></div>

## Unreliable Data

Data is almost universally less accurate than claimed—physical constants exceed their announced error bars by factors of 5 on average, economic data can differ by more than two-to-one between reporters, and laboratory 'fine-tuning for low variance' systematically biases accuracy claims—and the practical response is to pre-test all data for inconsistency before processing it, and to prefer small carefully-taken samples over large poorly-done ones.

* <span id="the-art-of-doing-science-and-engineering-learning--093"></span>**Physical constants in standard tables are not remotely as accurate as their listed uncertainties claim—the average later measurement falls 5.267 times outside the earlier stated error bounds—because standard laboratory practice of fine-tuning for low variance produces artificially narrow confidence intervals, not accurate ones.**
    - Hamming's rule: 90% of the time, the next independent measurement will fall outside the previous 90% confidence limits—a deliberate overstatement to make the rule memorable, but based on a lifetime of observing measurement accuracy.
    - Hubble's constant measurements regularly fall outside the stated uncertainties of other measurements—fundamental cosmological data has the same problem.
* <span id="the-art-of-doing-science-and-engineering-learning--094"></span>**Economic data is especially unreliable: official gold-flow figures between countries differ by more than two-to-one between reporter and receiver, GNP counts DuPont's GM stock holdings twice, inventory reporting rules change without notice but move key economic indices, and discount practices make cost data systematically biased in recession vs. expansion.**
    - Morgenstern's On the Accuracy of Economic Measurements documents these problems systematically; most economists are unwilling to discuss the fundamental inaccuracy of their data.
    - Poverty statistics are self-defeating: as society upgrades the poverty definition, achieving the elimination target becomes permanently impossible.
* <span id="the-art-of-doing-science-and-engineering-learning--095"></span>**Small carefully-taken samples are better than large poorly-done ones—both cheaper and more accurate—a fact known but consistently ignored by management, who prefer 100% surveys; questionnaires are especially unreliable because phrasing, sequence, and who administers them systematically affect answers.**
    - Telephone and airline companies eventually accepted that small carefully-selected samples could distribute billing revenue between partners more accurately than large cumbersome full surveys.
    - Good researchers know that high-ranking visitors change what is happening in their presence, and data gathered while they are present reflects what subordinates think they want to see.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_lunar-cycle-row.png" alt="" role="presentation" loading="lazy"></div>

## Systems Engineering

Systems engineering is the disciplined practice of keeping the larger goal in mind at all times—resisting the systematic tendency to optimize components at the expense of system performance—and its central paradox is that there is neither a fixed problem nor a final solution: each solution changes the environment and reveals deeper problems, making evolution rather than completion the natural state.

* <span id="the-art-of-doing-science-and-engineering-learning--096"></span>**The first rule of systems engineering is: if you optimize the components, you will probably ruin the system performance—demonstrated by improved amplifiers causing ground-leakage back-circuits in a differential analyzer, and by students cramming for individual courses while undermining their total education.**
    - A 4×4 square with amplifier improvements caused system failures by introducing back-circuit leakage through inadequate grounding—adding a heavier copper ground fixed it, but the improvement of an apparently self-standing component still ruined the system.
    - The University of Chicago's nine-course integrated exam system forced students to learn material for retention rather than for passing one course at a time—the system approach to education.
* <span id="the-art-of-doing-science-and-engineering-learning--097"></span>**Systems engineering design must prepare for graceful change—flexibility built into the initial design handles both later upgrades and the inevitable field changes during installation—because the presence of the solution changes the environment and generates new requirements immediately.**
    - The Nike missile system required a constant stream of field changes even during initial installation at Kwajalein Island.
    - The Venetian arsenal (~1200–1400 AD) operated a production line where each ship received ropes, masts, sails, and a trained crew at the right moment as it came down the line—an early 'just in time' system that included human training as a component.
* <span id="the-art-of-doing-science-and-engineering-learning--098"></span>**Systems engineering problems have neither fixed boundaries nor final solutions—each solution round provides deeper understanding of the real problem, and the client's stated symptoms are rarely the true cause; the systems engineer's job is to move from symptoms to causes while keeping the client's long-term interests in view.**
    - Westerman's ten essays on systems engineering conclude that the job is never done because the solved problem changes the environment, generating new problems, and because the solving process itself deepens insight into what was really needed.
    - The Nike project evolved from 'shoot down a single airplane' to 'coordinate a battery of missiles' to 'decide which cities to defend in proportion to enemy damage potential'—each solution revealing that the real problem was different from the stated one.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_moon-phases.png" alt="" role="presentation" loading="lazy"></div>

## You Get What You Measure

The choice of measurement scale controls what happens in an organization far more than most designers of rating systems realize: high-floor rating scales promote risk-aversion, uniform-distribution grading maximizes information, and optimizing individual-level metrics consistently damages system-level performance—making measurement design one of the highest-leverage and most neglected aspects of organizational management.

* <span id="the-art-of-doing-science-and-engineering-learning--099"></span>**Rating systems with a high floor (e.g., starting at 95%) structurally select for risk-aversion at all levels, because there is little to gain by risk-taking but much to lose, producing a population of conservative survivors who rise to positions requiring exactly the risk-tolerance that was systematically eliminated.**
    - Starting at 20% would encourage risk-taking: with so little to lose and so much to gain, people would try bold moves, and the survivors would be genuine risk-takers.
    - The Richter scale uses log(energy), compressing large earthquakes and expanding small ones—a nonlinear transformation that changes what the distribution of earthquakes 'looks like' and what conclusions are drawn.
* <span id="the-art-of-doing-science-and-engineering-learning--100"></span>**Using the full dynamic range of a rating scale gives you disproportionate influence in blind averaging—and from information theory, the entropy (information transmitted) is maximum when all grades are used equally, meaning typical grade inflation (mainly A and B) destroys most of the information value of grades.**
    - If you assign a 6 to what you like while a reviewer who dislikes it assigns 2, the average is 4—your positive evaluation is more than wiped out by the full-dynamic-range negative.
    - The Naval Academy's use of class rank is the only real defense against grade inflation, though it forces someone to the bottom even in an outstanding class.
* <span id="the-art-of-doing-science-and-engineering-learning--101"></span>**Measuring software productivity by lines of code is a counter-incentive to clean, compact code—programmers maximize lines because that is what is measured—illustrating the general principle that any metric becomes a target once instituted, and people will optimize the metric at the expense of the actual goal.**
    - Lines-of-code metrics are one reason why modern software systems are so bloated: there is every incentive to leave excess code in and add bells and whistles.
    - Many reporting systems have the effect of training people to prepare for periodic inspection rather than for constant readiness—military ship inspections being the paradigmatic example.


<div class="chapter-glyph"><img src="/glyphs/Science/Space_person-on-planet.png" alt="" role="presentation" loading="lazy"></div>

## You and Your Research

Doing significant work is primarily a matter of preparation, drive, and vision—not luck or extraordinary IQ—and the key practices are: working on important problems, building courage to pursue them, tolerating ambiguity, maintaining a list of 10–20 fundamental unsolved problems, taking time weekly to think about the big picture, and presenting work in ways that let others build on it.

* <span id="the-art-of-doing-science-and-engineering-learning--102"></span>**Great people repeatedly produce great work—Shannon, Einstein, Newton—which refutes the pure-luck hypothesis; what distinguishes them is that they prepared themselves through sustained hard work, and Pasteur's 'luck favors the prepared mind' captures both the role of luck and the role of preparation.**
    - Einstein asked himself as a 12-year-old what light would look like if he traveled at its speed—an obvious contradiction with Maxwell's equations—and was thereby prepared to understand special relativity better than anyone else when he finally attacked it.
    - Shannon created both information theory AND coding theory in the same period, and his master's thesis applied Boolean algebra to switching circuits—a pattern of multiple breakthroughs inconsistent with pure luck.
* <span id="the-art-of-doing-science-and-engineering-learning--103"></span>**Working on important problems—not just hard ones—is essential; most scientists spend most of their time on problems they believe are neither important nor likely to lead to important things, and no one has ever explained to Hamming why this is rational.**
    - After asking chemists at lunch what the important problems in chemistry were, then what they were working on, then why they were working on unimportant things, Hamming was no longer welcome at the chemistry table—but one chemist thought about it all summer and was soon promoted.
    - A problem is important partly because there is a possible attack on it, not just because of its inherent importance—anti-gravity and time travel are important but not currently workable.
* <span id="the-art-of-doing-science-and-engineering-learning--104"></span>**Taking 10% of time (Friday afternoons) to think about the big picture—where computing was heading, what role it would play in science and society—kept Hamming from drifting randomly and allowed him to direct his major efforts toward the right problems rather than merely the current ones.**
    - Drive matters: intellectual investment compounds like interest—one extra hour per day over a lifetime far more than doubles total output because each year you know more and can do more.
    - Great people maintain a list of 10–20 fundamental unsolved problems; when a clue appears they drop other things immediately and work on the important problem, which is why they tend to come in first.
* <span id="the-art-of-doing-science-and-engineering-learning--105"></span>**Doing your work 'with style'—presenting results in fundamental form so others can build on them, selling ideas through clear written and oral presentation, and never making yourself indispensable (which prevents promotion)—is as important as doing the work in the first place.**
    - When Hamming realized he was demonstrating that digital computers could beat analog computers on their home ground, he rewrote the integration method into a clean publishable form—'Hamming's method'—rather than just submitting results.
    - Change does not mean progress, but progress requires change—and to sell change you must master formal presentations, written reports, and the art of informal presentations.
* <span id="the-art-of-doing-science-and-engineering-learning--106"></span>**The effort required for excellence is worth it not primarily for the achievement but for who you become in the struggle—and the most important realization is that it is generally easier to succeed than it first appears, since around every person there is a halo of opportunities waiting to be recognized.**
    - The chief gain is in the effort to change yourself, in the struggle with yourself, and it is less in the winning than you might expect.
    - "I have now told you in some detail how to succeed, hence you have no excuse for not doing better than I did." —Hamming
