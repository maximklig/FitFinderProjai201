# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
This tool/function returns three matching listings sorted by relevance given the users
specificities and exact wants. 

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): Refers to the description of the item and descriptive tags.
- `size` (str): Refers to the size of the item represented by a single Char e.g. 'M', 'L'
- `max_price` (float): Refers to the Max price the user is willing to pay. Items above the specified number will not be shown.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
The return value will contain the name/description of the item, the price, the source, and the condition of the item.

**What happens if it fails or returns nothing:**
The agent should notify the user "No such items found following specifications", or something along those lines. 
Pretty much the agent should return a sentence clarifying that with the specific condition given, no items were able to
found. 

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): New item relates to the specific clothing item the user wishes to style with other clothes within 
their wardrobe
- `wardrobe` (dict): an array of the users saved items within the wardrobe highlighting the users style and prefrences 
regarding clothes. 

**What it returns:**
What is returned is a stylistic evaluations on the back end of things of which items within the users wardrobe would 
best compliment the item given within the arguments (new_item). There can be variance with every different output but 
specific tags such as descriptive tags, stylistic choices, and size should be curated carefully each time reflecting
the current trends.

**What happens if it fails or returns nothing:**
If no items can be combined to make a good outfit then a simple phrase such as "Sorry, I'm having difficulty pairing 
clothes from your wardrobe. Please try again with another item." is more than enough than throwing an error.

---

### Tool 3: create_fit_card

**What it does:**
This function returns 2-4 sentences describing the fit built from the usage of the two tool: suggest_outfit and 
search_listings when these tools are used in succession. The caption has to feel natural and refrain from sounding as
a product placement. 

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (String outfit(return value of suggest_outfit), new_item (dict)): The outfit stylized from suggest_outfit 
is now used to paint a clear picture of its involvement in a certain style.

**What it returns:**
This function feeds the llm the suggested_outfit combination string from suggest_outfit() function with conjuction of 
the new_item found in search_listings and generates 2-4 sentences referring to the curation of the "fit", how all the 
clothes work together, the differing factors that make this outfit work, and the specific mood/vibe curated by the 
collection of these clothes. The specific clothing item from new_item, platform / source in which new_item was found,
and price MUST be mentioned in a natural way. These factors may be only brought up once respectively. 

**What happens if it fails or returns nothing:**
If outfit data in incomplete then the return should simply state that "I am unable to curate a caption based on what 
was given". Depending on the data, the return value can spec into specifics such as the user having nothing within their 
respective wardrobe or simply insufficient variables to work with. 

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
 
If the user asks for a recommendation, or that they are looking for something, those keywords tell the llm that the user is searching
hence they are looking for relevancy.
to specify a vibe or mood with articles of clothing from the users wardrobe in conjuction with a piece of clothing found signifies to the 
agent to call suggest_outfit to utilize both those arguments. 

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

Within tool one the database of listings.json is parsed through. Given the users parameters multiple relevant listings are found and one is chosen
by the user. 
Once that one listing is chosen, the id is saved and used in the second tool (suggest_outfit()). Within suggest outfit, the curated outfit is then 
saved as its own string. Utilizing what the user has said in he query for fit curation and the chosen articles of clothing, the third tool is called
(if the user wishes to make a caption) and the llm will process the articles of clothing alongside the users query and generate a natural sounding 
caption.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response                                                              |
|------|-------------|-----------------------------------------------------------------------------|
| search_listings | No results match the query | "There are no relevant searches, you must modify what you are looking for." |
| suggest_outfit | Wardrobe is empty | "In order to curate a 'fit', there must be items added in your wardrobe."   |
| create_fit_card | Outfit input is missing or incomplete | "Please reinput your outfit."                                                |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

User Query
(natural language: item description, size, budget, wardrobe context)
    │
    ▼
Planning Loop
(parses intent, reads session state after each tool call, terminates when fit_card is set)
    │
    ▼
search_listings(description: str, size: str, max_price: float)
    │ returns: top 3 items (name, price, source, condition)
    ├──[no results]──► "No items found following specifications." → prompt user to refine
    │
    ▼
User selects one of the 3 listings
    │ session: selected_item = chosen item dict
    ▼
suggest_outfit(new_item: selected_item, wardrobe: dict[])
    │ returns: outfit suggestion string (wardrobe pairings by tags, style, size, trends)
    ├──[empty wardrobe / no match]──► "Having difficulty pairing clothes. Try another item."
    │
    ▼ session: outfit_suggestion = "..."
    │
create_fit_card(outfit: outfit_suggestion, new_item: selected_item)
    │ returns: 2–4 sentence caption (item name, source, price each mentioned once naturally)
    ├──[incomplete data]──► "Unable to curate a caption based on what was given."
    │
    ▼ session: fit_card = "..."
    │
Final Output
  1. Top 3 listings
  2. Outfit suggestion from wardrobe
  3. Fit card caption

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

For the actual implementation of the three tools I plan to use Claude (Claude Code) since it can read
my whole repo and not just a snippet I paste in. What I'll give it is each tools spec straight from the
sections above (the inputs, the return value, and most importantly the failure mode) alongside the
listings.json and wardrobe_schema.json so it knows the exact field names it has to work with. I'll also
point it at utils/data_loader.py and tell it to use load_listings() instead of re writing the file loading
since that is already done for me.

For search_listings I expect it to load the listings, filter by max_price and size first, then score whats
left by keyword overlap with the description and drop anything that scores 0 so I don't get irrelevant junk,
then sort highest score first. The way I'll verify it matches my spec is by running it on a couple queries
before trusting it. "vintage graphic tee" under 50 should give me results, "designer ballgown" size XXS
under 5 should give me an empty list and NOT throw, and a price filter like under 10 should never return
something priced above 10. Those are basically my failure modes from the error table so if those pass im happy.

For suggest_outfit and create_fit_card these both call the llm (Groq llama-3.3-70b-versatile with my
GROQ_API_KEY in conjuction with the .env file) so the thing I care most about is that they don't crash. For
suggest_outfit the empty wardrobe case has to be handled gracefully, if the user has no items saved it should
still give general styling advice instead of erroring out. For create_fit_card if the outfit string comes in
empty it should return an error message string and not raise. I'll verify create_fit_card by running it a few
times on the SAME input and checking the captions actually come out different, and if they're identical I'll
bump the temperature up untill there's variance (used a higher temperature for this exact reason). I'll also
write pytest tests in a tests/ folder, at least one test per failure mode, so I can re run them later and know
nothing broke.

**Milestone 4 — Planning loop and state management:**

For the planning loop in agent.py I'll hand Claude my Architecture diagram and the Planning Loop / State
Management sections above so the code it writes follows the same flow I already drew out, not some random
order. The input to the loop is the natural language query plus the wardrobe dict, and the single source of
truth for the whole interaction is the session dict from _new_session() (that holds the query, the parsed
params, the search results, the selected item, the outfit suggestion, the fit_card and an error field).

For the parsing step itself I went with plain regex instead of asking the llm to parse the query. Two reasons,
it stays deterministic so the same query always parses the same way, and it doesn't burn an api call (or need
the key at all) just to pull out a price and a size. The regex grabs max_price off phrases like "under $30" or
a bare "$30", and size off "size M" or a standalone known size token, and whatevers left becomes the
description that gets fed to search_listings.

The flow I expect it to produce: first parse the query into description / size / max_price and store that in
session["parsed"], then call search_listings with those params. If search comes back empty I want it to set
session["error"] to a helpful message and return early, the whole point is it should NOT keep going into
suggest_outfit with nothing to work with. If there are results it picks the top one as selected_item, feeds
that plus the wardrobe into suggest_outfit and saves the string, then feeds that outfit string plus the
selected_item into create_fit_card and saves the caption. State gets passed forward purely through the session
dict, each tool reads what the last one wrote into it, and the loop knows its done once fit_card is set (or it
bailed early because of an error).

How I'll verify it matches my spec is by running agent.py directly. The happy path query ("vintage graphic tee
under 30") should fill in selected_item, outfit_suggestion and fit_card with error staying None, and the
no results path ("designer ballgown size XXS under 5") should come back with just an error message set and the
other fields left None. If both of those behave that way then the state is flowing the way I planned it.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** 
"I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
The agent first breaks apart the sentence to define certain requirements that the user requests. Within the example user
query descriptive tags such as, under 30$, vintage graphic tee will be utilized in the the suggest_listing tool call.  
"I mostly wear baggy Jeans and chunky sneakers" will be kept in memory for the ai to utilize later when we call 
suggest_outfit tool. 
**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
From step one we get a list of relevant searches, for this project the function will return the top 3 relevant searches
and the user will choose which of these best suits their need. If none of them are to their standard they have a choice 
modify their prompt or specific factors that they would like to change. Assuming that the user is content with their
choice and chooses one of the options given, then a prompt to whether the user wants a curation of that item with their 
wardrobe is prompted (assuming the user says yes) and recalling what they said earlier in reference to their wardrobe 
suggest_outfit is called and ran with the output being a non empty string with outfit suggestions.
**Step 3:**
<!-- Continue until the full interaction is complete -->
Now that the user has recieved their return value string from tool #2 (suggest_outfit) that return value alongside 
new_item are taken in as arguments and return value will be a string of 2-4 sentences emulating a caption the user or
a user would have posted on social media sites such as snapchat or instagram. 
**Final output to user:**
<!-- What does the user actually see at the end? -->
Final output:
3 relevant clothing articles procured through user parameters
    Then a string return of what outfits within the users wardrobe (taken from wardrobe_schema.json) accurately match
    thr users descriptive tags regarding the clothing article they chose.
    Lastly a string return of a caption, 2-4 sentences written, describing the outfit and other specifics (can be found
    in previous sections of text) in a natural and unartificial tone. 
