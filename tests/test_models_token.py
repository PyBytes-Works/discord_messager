import unittest
from unittest import TestCase
import datetime

from models import Token, UserChannel, User, Channel, TokenPair
test_user={
    'telegram_id': '123',
    'nick_name': 'test_name_123',
    'first_name': '',
    'last_name': '',
    'active': 1,
    'is_work': 1,
    'admin': 1,
    'max_tokens': 5,
    'expiration': datetime.datetime.now().timestamp() + 30+24+60+60,
    'proxy': 'test_proxy1'
}

test_channel = {
    'channel': '12345',
    'guild': '12345'
}

test_user_channel = {
    'name': 'test_user_channel1',
    'cooldown': 3*60,
}

test_token = {
    'first': {
                'name': 'test_name_token1',
                'token': 'test_token1',
                'discord_id': 'test_discord_id1',
            },
    'second': {
                'name': 'test_name_token2',
                'token': 'test_token2',
                'discord_id': 'test_discord_id2',
            },
    'third': {
                'name': 'test_name_token3',
                'token': 'test_token3',
                'discord_id': 'test_discord_id3',
            },
    'fourth': {
                'name': 'test_name_token4',
                'token': 'test_token4',
                'discord_id': 'test_discord_id4',
            }
}


class TestToken(TestCase):
    def setUp(self) -> None:
        self.user = User.create(**test_user)
        self.channel = Channel.create(**test_channel)
        self.user_channel = UserChannel.create(
            user=self.user,channel=self.channel,**test_user_channel)
        for token in test_token.values():
            Token.add_token(
                name=token['name'],
                discord_id=token['discord_id'],
                user_channel=self.user_channel,
                token=token['token'],
            )
        self.first_token: Token = Token.get_or_none(
            Token.name==test_token['first']['name'],
            Token.discord_id==test_token['first']['discord_id'],
            Token.token==test_token['first']['token']
        )
        self.second_token: Token = Token.get_or_none(
            Token.name==test_token['second']['name'],
            Token.discord_id==test_token['second']['discord_id'],
            Token.token==test_token['second']['token']
        )
        self.thrid_token: Token = Token.get_or_none(
            Token.name==test_token['third']['name'],
            Token.discord_id==test_token['third']['discord_id'],
            Token.token==test_token['third']['token']
        )
        self.fourth_token: Token = Token.get_or_none(
            Token.name==test_token['fourth']['name'],
            Token.discord_id==test_token['fourth']['discord_id'],
            Token.token==test_token['fourth']['token']
        )
        self.token_pair = None
        self.token_pair_delete_test = None

    def test_add_token_by_user_channel(self):
        self.assertEqual(self.first_token.token, test_token['first']['token'])
        self.assertEqual(self.first_token.user_channel.name, test_user_channel['name'])

    def test_update_token_time(self):
        expect = datetime.datetime.now().timestamp()
        answer = Token.update_token_last_message_time(token=test_token['first']['token'])
        self.assertEqual(answer, 1)
        actual = (
                    Token.select()
                        .where(Token.token == test_token['first']['token'])
                        .first().last_message_time.timestamp()
                  )
        self.assertAlmostEqual(int(expect), int(actual), places=0, delta=2)

    def test_make_tokens_pair(self):
        answer = Token.make_tokens_pair(first=self.first_token.token, second=self.second_token.token)
        self.token_pair = TokenPair.get_or_none(
            TokenPair.first_id.in_((self.first_token.id, self.second_token.id)))
        self.assertTrue(answer)
        self.assertTrue(
            self.token_pair.first_id.token
            in
            (test_token['first']['token'], test_token['second']['token'])
        )

    def test_delete_token_pair(self):
        answer = Token.make_tokens_pair(first=self.thrid_token.token, second=self.fourth_token.token)
        self.token_pair_delete_test = TokenPair.get_or_none(
            TokenPair.first_id.in_((self.thrid_token.id, self.fourth_token.id)))
        result = Token.delete_token_pair(self.thrid_token.token)
        self.assertTrue(answer)
        self.assertTrue(result)
        self.assertFalse(
            TokenPair.get_or_none(TokenPair.first_id.in_((self.thrid_token.id, self.fourth_token.id)))
        )
        self.assertFalse(
            TokenPair.get_or_none(TokenPair.second_id.in_((self.thrid_token.id, self.fourth_token.id)))
        )

    def tearDown(self) -> None:
        self.token_pair and self.token_pair.delete_instance()
        self.token_pair_delete_test and self.token_pair_delete_test.delete_instance()
        self.first_token and self.first_token.delete_instance()
        self.second_token and self.second_token.delete_instance()
        self.thrid_token and self.thrid_token.delete_instance()
        self.fourth_token and self.fourth_token.delete_instance()
        self.user_channel and self.user_channel.delete_instance()
        self.channel and self.channel.delete_instance()
        self.user and self.user.delete_instance()


if __name__ == '__main__':
    unittest.main()
