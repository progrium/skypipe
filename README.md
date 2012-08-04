# Skypipe (work in progress!!)

Skypipe is a command line tool that lets you easily pipe data across terminal sessions, regardless of whether that session is on the same machine or not. It gives you named pipes in the sky and lets you pipe data *anywhere*. 

Skypipe combines named pipes and netcat and gives you even more power in a simpler tool. Here is a simple example using an unnamed skypipe like you would a regular named pipe in order to gzip a file across shells:

	$ skypipe.rb | gzip -9 -c > out.gz

Your skypipe is ready to receive some data from another shell process:

	$ cat file | skypipe.rb

Unliked named pipes, however, *this will work across any machines connected to the Internet*. And you didn't have to specify a host address or set up "listen mode" like you would with netcat. In fact, unlike netcat, which is point to point, you could use skypipe for log aggregation. Here we'll used named skypipes. Run this on several hosts:

	$ tail -f /var/log/somefile | skypipe.rb logs

And then run this on a single machine:
	
	$ skypipe.rb logs > /var/log/aggregate

Or alternatively you can broadcast to multiple hosts. With the above, you can "listen in" by running this from your laptop, even while behind a NAT:

	$ skypipe.rb logs

Also unlike netcat, you can temporarily store data "in the pipe" until you pull it out. In fact, you can keep several "files" in the pipe. On one machine load some files into it a named skypipe:

	$ cat file_a | skypipe.rb files
	$ cat file_b | skypipe.rb files

Now from somewhere else pull them out, in order:

	$ skypipe.rb files > new_file_a
	$ skypipe.rb files > new_file_b

Lastly, you can use skypipe like the channel primitive in Go for coordinating between shell scripts. As a simple example, here we use skypipe to wait for an event triggered by another script:

	#!/bin/bash
	echo "I'm going to wait until triggered"
	skypipe.rb trigger
	echo "I was triggered!"

Triggering is just sending an EOF over the pipe, causing the listening skypipe to terminate. We can do this with a simple idiom:

	$ echo | skypipe.rb trigger
