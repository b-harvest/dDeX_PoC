#!/usr/bin/env python3

from flask import Flask, render_template, request, redirect, url_for
import redis
import time, datetime
import json
import subprocess

app = Flask(__name__)
r = redis.Redis(host="localhost", port=6379, db=0)
key_password = "123123123"
chain_id = "chain-hackatom-b-harvest"
seller_key = "seller"
buyer_key = "buyer"
buyer_addr_default = "cosmos17mce34nfzl85jfeyhnqs336peppacgnsy9vqkn"
seller_addr_default = "cosmos1hjwxa8qjzrq3f4y4nvm3jv3pq03mm20fra4zn8"
valoper_addr_default = "cosmosvaloper1zy945fyxgasuvgjfh4m5r3qq5wjpvsdld2qey5"

# get signature from testnet node
def get_sign_string(key_name, tx_json_string):

    with open("tx.json","w+") as f:
        f.write(tx_json_string)
    time.sleep(1)

    cmd = "echo " + key_password + " | gaiacli tx sign tx.json --from " + str(key_name) + " --chain-id chain-hackatom-b-harvest --signature-only --output json"
    result_string = json.dumps(json.loads(subprocess.check_output(cmd, shell=True).decode("utf-8")),sort_keys=False)
    return result_string

# get detail info from tx
def get_tx_data(tx_hash):

    cmd = "gaiacli q tx " + tx_hash + " --chain-id chain-hackatom-b-harvest --output json"
    result = json.loads(subprocess.check_output(cmd, shell=True).decode("utf-8"))

    return result

# listing existing trades
@app.route("/")
def market():

    if r.exists("last_index"):
        last_index = int(r.get("last_index").decode("utf-8"))
    else:
        last_index = 0

    print(last_index)

    trades = []
    for i in range(0,last_index+1):
        if r.exists("trade_" + str(i)):
            trade = json.loads(r.get("trade_" + str(i)).decode("utf-8"))
            trades.append(trade)

    trades = sorted(trades, key=lambda k: k["upload_timestamp"], reverse=True)

    return render_template("market_status.html",trades=trades,current_time=time.time())

# displaying current asset status of each address
@app.route("/balance")
def balance():

    cmd = "gaiacli q staking delegation "+seller_addr_default+" "+valoper_addr_default+" --chain-id chain-hackatom-b-harvest --output json"
    seller_stake_result = json.loads(subprocess.check_output(cmd, shell=True).decode("utf-8"))
    cmd = "gaiacli q account "+seller_addr_default+" --chain-id chain-hackatom-b-harvest --output json"
    seller_balance_result = json.loads(subprocess.check_output(cmd, shell=True).decode("utf-8"))
    cmd = "gaiacli q staking delegation "+buyer_addr_default+" "+valoper_addr_default+" --chain-id chain-hackatom-b-harvest --output json"
    buyer_stake_result = json.loads(subprocess.check_output(cmd, shell=True).decode("utf-8"))
    cmd = "gaiacli q account "+buyer_addr_default+" --chain-id chain-hackatom-b-harvest --output json"
    buyer_balance_result = json.loads(subprocess.check_output(cmd, shell=True).decode("utf-8"))

    seller_stake = 0
    buyer_stake = 0
    seller_balance = 0
    buyer_balance = 0

    if len(seller_stake_result)>0:
        seller_stake = int(float(seller_stake_result["shares"]))
    if len(buyer_stake_result)>0:
        buyer_stake = int(float(buyer_stake_result["shares"]))
    if len(seller_balance_result["value"]["coins"])>0:
        for coin in seller_balance_result["value"]["coins"]:
            if coin["denom"] == "uatom":
                seller_balance += int(float(coin["amount"]))
    if len(buyer_balance_result["value"]["coins"])>0:
        for coin in buyer_balance_result["value"]["coins"]:
            if coin["denom"] == "uatom":
                buyer_balance += int(float(coin["amount"]))

    balance_data = {"seller_address":seller_addr_default, "buyer_address":buyer_addr_default, "valoper_address":valoper_addr_default, \
                    "seller_stake":seller_stake, "buyer_stake":buyer_stake, "seller_balance":seller_balance, "buyer_balance":buyer_balance}

    return render_template("market_balance.html",balance_data=balance_data)

# display tx result
@app.route("/tx", methods=["GET"])
def market_tx():

    tx_hash = str(request.args.get("tx_hash"))
    tx_result = get_tx_data(tx_hash)
    tx_result_string = json.dumps(tx_result,sort_keys=False, indent=4)

    return render_template("market_tx.html",tx_result_string=tx_result_string)

# post a new delegation sale
@app.route("/market_new_seller")
def market_new_seller():

    return render_template("market_new_seller.html")

# submit a new delegation sale
@app.route("/market_new_seller_submit", methods=["GET"])
def market_new_seller_submit():

    seller_address = str(request.args.get("seller_address"))
    price = float(request.args.get("price"))
    valoper = str(request.args.get("valoper"))
    trade_amount = int(request.args.get("trade_amount"))

    if r.exists("last_index"):
        last_index = int(r.get("last_index").decode("utf-8"))
    else:
        last_index = 0

    trade = {"index":last_index+1, "upload_timestamp":int(time.time()),"upload_time":str(datetime.datetime.now()), "status":"live", \
             "terms":{"seller_address":seller_address,"valoper":valoper,"price":price,"trade_amount":trade_amount,"buyer_address":""}, \
             "tx_sig":{"tx_json_string":"","buyer_sig":"","seller_sig":""}, \
             "trade_result":{"tx_hash":"","commit_block":"","success_flag":False}}

    r.set("trade_"+str(last_index+1),json.dumps(trade,sort_keys=False))
    r.set("last_index",last_index+1)

    return redirect(url_for("market"))

# process delegation sale from seller side
@app.route("/market_view_my_sell", methods=["GET"])
def market_view_my_sell():

    index = request.args.get("index")
    trade = json.loads(r.get("trade_" + str(index)).decode("utf-8"))
    tx_json_string = trade["tx_sig"]["tx_json_string"]
    seller_sig_string = ""
    if tx_json_string != "":
        seller_sig_string = get_sign_string("seller", tx_json_string)

    return render_template("market_view_my_sell.html", trade=trade, seller_sig_string=seller_sig_string)

# process delegation buy from buyer side
@app.route("/market_buy_bid", methods=["GET"])
def market_buy_bid():
    index = request.args.get("index")
    trade = json.loads(r.get("trade_" + str(index)).decode("utf-8"))
    buyer_address = str(request.args.get("buyer_address"))
    seller_address = trade["terms"]["seller_address"]
    valoper = trade["terms"]["valoper"]
    price = float(trade["terms"]["price"])
    trade_amount = float(trade["terms"]["trade_amount"])

    if buyer_address == "None": # buyer"s information not submitted yet
        return render_template("market_buy_bid.html",index=index, trade=trade, current_time=time.time())
    else: # buyer"s information submitted
        buyer_sig = str(request.args.get("buyer_sig"))
        tx_json = {
          "type": "auth/StdTx",
          "value": {
            "msg": [
              {
                "type": "cosmos-sdk/MsgChangeDelegator",
                "value": {
                  "delegator_src_address": str(seller_address),
                  "delegator_dst_address": str(buyer_address),
                  "validator_address": str(valoper),
                  "amount": {
                      "denom": "uatom",
                      "amount": str(int(trade_amount))
                  }
                }
              },
              {
                "type": "cosmos-sdk/MsgSend",
                "value": {
                  "from_address": str(buyer_address),
                  "to_address": str(seller_address),
                  "amount": [
                    {
                      "denom": "uatom",
                      "amount": str(int(price))
                    }
                  ]
                }
              }
            ],
            "fee": {
              "amount": None,
              "gas": "200000"
            },
            "signatures": None,
            "memo": "trade_" + str(index)
          }
        }

        tx_json_string = json.dumps(tx_json,sort_keys=False)

        trade["terms"]["buyer_address"] = buyer_address
        trade["tx_sig"]["buyer_sig"] = buyer_sig
        trade["tx_sig"]["tx_json_string"] = tx_json_string


        if buyer_sig == "None": # provide tx_json, no signature submitted yet
            buyer_sig_string = get_sign_string("buyer", tx_json_string)
            return render_template("market_buy_bid.html",index=index, trade=trade, buyer_sig_string=buyer_sig_string, current_time=time.time())
        else: # signature submitted
            trade["tx_sig"]["tx_json_string"] = tx_json_string
            trade["terms"]["buyer_address"] = buyer_address
            trade["tx_sig"]["buyer_sig"] = buyer_sig
            trade["status"] = "trading"
            r.set("trade_"+str(index),json.dumps(trade,sort_keys=False))
            return redirect(url_for("market"))

# confirm the trade and broadcast
@app.route("/market_trade_confirm", methods=["GET"])
def market_trade_confirm():

    index = request.args.get("index")
    trade = json.loads(r.get("trade_" + str(index)).decode("utf-8"))
    seller_sig = str(request.args.get("seller_sig"))
    trade["tx_sig"]["seller_sig"] = seller_sig
    trade["status"] = "done"

    tx_json_string = trade["tx_sig"]["tx_json_string"]
    tx_json = json.loads(tx_json_string)

    buyer_sig_json = json.loads(trade["tx_sig"]["buyer_sig"])
    seller_sig_json = json.loads(trade["tx_sig"]["seller_sig"])

    tx_json["value"]["signatures"] = [seller_sig_json,buyer_sig_json]
    tx_json_string = json.dumps(tx_json,sort_keys=False)

    with open("tx_signed.json","+w") as f:
        f.write(tx_json_string)
    time.sleep(1)

    cmd = "sudo gaiacli tx broadcast tx_signed.json --chain-id chain-hackatom-b-harvest --output json"
    result = json.loads(subprocess.check_output(cmd, shell=True).decode("utf-8"))
    tx_hash = result["txhash"]

    time.sleep(10)

    tx_result = get_tx_data(tx_hash)
    tx_height = tx_result["height"]
    tx_success = tx_result["logs"][0]["success"]

    trade["trade_result"]["tx_hash"] = tx_hash
    trade["trade_result"]["commit_block"] = tx_height
    trade["trade_result"]["success_flag"] = tx_success

    r.set("trade_"+str(index),json.dumps(trade,sort_keys=False))

    return redirect(url_for("market"))

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
