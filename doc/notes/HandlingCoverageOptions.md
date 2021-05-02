
Much as with other aspects of PyVSC, there are two aspects to 
coverage options: the user facade and the model. Settings must
be properly-propagated between these two. When it comes to
coverage options, the intent is for these to cascade. Options
specified at the covergroup level cascade down to the coverpoint
in the absence of a coverpoint-specific setting. Options
specified at the coverpoint level override options specified
at the covergroup level.

Options are collected at the covergroup and coverpoint level
during facade construction. At this point, there is no 
connection between these options. 

During model construction, the covergroup model is created first.
A set of model options is constructed based on defaults and
value specified by the user.

Next, coverpoints are create. Here, also, options are created
based on defaults, covergroup options, and coverpoint options
specified by the user.
