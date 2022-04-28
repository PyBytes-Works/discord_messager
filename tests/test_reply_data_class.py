from classes.replies import ReplyData


def test_set_answered():
    print("\ntest_set_answered")
    print("Before:", reply.answered)
    reply.set_answered()
    print("After", reply.answered)


def test_set_showed():
    print("\ntest_set_showed")
    print("Before:", reply.showed)
    reply.set_showed()
    print("After", reply.showed)


def test_get_dict():
    print("\ntest_as_dict")
    result = reply.get_dict()
    print("Result type:", type(result))
    print("Result:", result)
    print(f"\nToken: {result.get('token')}")
    print(f"author: {result.get('author')}")
    print(f"text: {result.get('text')}")
    print(f"message_id: {result.get('message_id')}")
    print(f"to_message: {result.get('to_message')}")
    print(f"to_user: {result.get('to_user')}")
    print(f"target_id: {result.get('target_id')}")
    print(f"answer_text: {result.get('answer_text')}")
    print(f"answered: {result.get('answered')}")
    print(f"showed: {result.get('showed')}")


if __name__ == '__main__':
    data = {
        "token": "OTMzMTE5MDYwNDIwNDc2OTM5.Yl_FVg.XWI4hOWUH8PleGLtDnmQdhCcmlw",
        "author": "Deskent",
        "text": "034957049",
        "message_id": "968108356243976252",
        "to_message": "I can not do it any longer)",
        "to_user": "Deskent mate",
        "target_id": "933119013775626302",
        "answer_text": "55555555555555555"
    }
    reply = ReplyData(**data)
    test_set_answered()
    test_set_showed()
    test_get_dict()
