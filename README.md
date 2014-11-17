# sharknado

[![Build Status](https://travis-ci.org/simock85/sharknado.svg)](https://travis-ci.org/simock85/sharknado)

sharknado is a super simple and super fast messaging server for the *Internet of Things* built with tornado and mongodb,
inspired by dweet.io, compatible with python 2.7, 3.2+ and pypy

It implements HAPI standards to provide web-based APIs that are machine ready but human/developer friendly.

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

## usage

Install the dependencies with pip:

    pip install -r requirements.txt

launch the server:

    python sharknado.py [OPTIONS]
    
options:

+ `port` binds the server to the given port. default 8000
+ `processes` number of processes to fork, 1: no child processes forked, 0: n_cpus processes, n: n processes. default 1
+ `mongo_uri` mongodb url. default mongodb://localhost:27017/sharknado
+ `messages_expire` expiration of messages, in seconds, 0 to disable expiration. default 1 month
+ `cors_origin` Access-Control-Allow-Origin header content. default "*", set to "" to disable cors

## tests

you can run the test suite using the tornado test runner:

    python -m tornado.testing tests.test_sharknado
    
you can also use your preferred runner :)

## hapi interface

### send messages

to send a message, just call a URL:

    send/message/for/my-thing-name?hello=world&foo=bar
    
Any query parameters you add to the request will be added as key-value pairs to the content of the message.
You can also send any valid JSON data in the body of the request with a POST.

sharknado will respond with

    {
      "this": "succeeded",
      "by": "sending",
      "the": "message",
      "with": {
        "_id": "5452180080cd99000268e0cb",
        "thing": "my-thing-name",
        "created": "2014-10-30T10:50:40.220000",
        "content": {
          "hello": "world",
          "foo": "bar"
        }
      }
    }
    
### retrieve messages

to retrieve messages, call the URL:

    get/messages/for/my-thing-name
    
sharknado will respond with

    {
      "this": "succeeded",
      "by": "getting",
      "the": "messages",
      "with": [
        {
          "_id": "5452180080cd99000268e0cf",
          "thing": "my-thing-name",
          "created": "2014-10-30T10:50:47.220000",
          "content": {
            "this": "is cool!"
          }
        },
        {
          "_id": "5452180080cd99000268e0cb",
          "thing": "my-thing-name",
          "created": "2014-10-30T10:50:40.220000",
          "content": {
            "hello": "world",
            "foo": "bar"
          }
        }
      ]
    }

by default sharknado will return messages from the past 30 days, you can override this behaviour by calling the url

    get/messages/for/my-thing-name/past/n-days
    
you can also retrieve only the latest message

    /get/latest/message/for/my-thing-name
    
### count messages

sharknado provides a fast message counter endpoint

    /count/messages/for/my-thing-name
    
## todo list

in no particular order:

+ message streaming
+ message locking
+ mongodb write concern customization
+ ~~support for python 3~~
