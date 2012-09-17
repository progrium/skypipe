# Skypipe (alpha)

Skypipe is a magical command line tool that lets you easily pipe data across terminal sessions, regardless of whether the sessions are on the same machine, across thousands of machines, or even behind a firewall. It gives you named pipes in the sky and lets you magically pipe data *anywhere*.

## Installing

Currently you need Python 2.6 and the ability to compile extensions.
Then install with pip from Github:

	$ pip install -e git+git://github.com/progrium/skypipe.git#egg=skypipe

## Setting up

The magic of skypipe requires a free dotcloud account. If you don't have
one, you can easily create one for free. The first time you use skypipe,
you will be asked for credentials. 

## Using Skypipe

Skypipe combines named pipes and netcat and gives you even more power in a simpler tool. Here is a simple example using skypipe like you would a named pipe in order to gzip a file across shells:

	$ skypipe | gzip -9 -c > out.gz

Your skypipe is ready to receive some data from another shell process:

	$ cat file | skypipe

Unliked named pipes, however, *this will work across any machines connected to the Internet*. And you didn't have to specify a host address or set up "listen mode" like you would with netcat. In fact, unlike netcat, which is point to point, you could use skypipe for log aggregation. Here we'll used named skypipes. Run this on several hosts:

	$ tail -f /var/log/somefile | skypipe logs

And then run this on a single machine:
	
	$ skypipe logs > /var/log/aggregate

Or alternatively you can broadcast to multiple hosts. With the above, you can "listen in" by running this from your laptop, even while behind a NAT:

	$ skypipe logs

Also unlike netcat, you can temporarily store data "in the pipe" until you pull it out. In fact, you can keep several "files" in the pipe. On one machine load some files into it a named skypipe:

	$ cat file_a | skypipe files
	$ cat file_b | skypipe files

Now from somewhere else pull them out, in order:

	$ skypipe files > new_file_a
	$ skypipe files > new_file_b

Lastly, you can use skypipe like the channel primitive in Go for coordinating between shell scripts. As a simple example, here we use skypipe to wait for an event triggered by another script:

	#!/bin/bash
	echo "I'm going to wait until triggered"
	skypipe trigger
	echo "I was triggered!"

Triggering is just sending an EOF over the pipe, causing the listening skypipe to terminate. We can do this with a simple idiom:

	$ echo | skypipe trigger

## Software with a service

The trick to this private pipe in the sky is that when you first use skypipe, behind the scenes it will deploy a very simple messaging server to dotcloud. Skypipe will use your account to transparently find and use this server, no matter where you are. 

This all works without you ever thinking about it because this server is managed automatically and runs on dotcloud for free. It might as well not exist!

This represents a new paradigm of creating tools that transparently leverage the cloud to create magical experiences. It's not quite software as a service, it's software *with* a service. Nobody is using a shared, central service. The software deploys its own service on your behalf for you to use. 

Thanks to platforms like dotcloud (and Heroku), we can now build software leveraging features of software as a service that is *packaged and distributed like normal open source software*.

## Contributing

There aren't any tests yet, but it's pretty well documented and the code
is written to be read. Fork and send pull requests. Check out the issues
to see how you can be most helpful.

## Contributors

* Jeff Lindsay <progrium@gmail.com>

## License

MIT
