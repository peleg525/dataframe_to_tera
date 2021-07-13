import teradatasql as t
import pandas as pd
import string
import math
from tqdm.notebook import tqdm
import numpy as np

class upload_to_tera:
    """
    Uploading large dataframes to tera
    
    """
    def __init__(self, df, q, table_name, memory=10000000):
        """
        ARGS:
        df - dataframe
        q - string - query
        table_name - string

        example format:
        q = Insert into d_digital_data.blabla values (?, ?, ?, ?)
        table_name = d_digital_data.blabla
        """
        self.memory = memory
        self.df = df
        self.rows = 0
        self.num = 0
        self.q = q
        self.l = []
        self.table_name = table_name
        self.alphabet_string = string.ascii_lowercase
        self.alphabet_list = list(self.alphabet_string) 
        self.bar = tqdm(total=len(df))
        with t.connect('{"host":"tdprd","logmech":"krb5"}') as con:
            with con.cursor () as cur:
                self.create_statment = cur.execute("show table " + table_name).fetchall()[0]
                self.create_statment = self.create_statment[0].replace('\r', '\n')
                cur.execute("delete " + table_name)
        self.upload_how_many_rows_we_want_main()
        
    def is_ascii(self, s):
        if all(ord(c) < 128 for c in s):
            return False
        return True

    
    def insert(self, q, df):
        with t.connect('{"host":"tdprd","logmech":"krb5"}') as con:
            with con.cursor () as cur:
                cur.execute(q, df.values.tolist())


    def upload_how_many_rows_we_want_main(self):
        """
        uploading large dataframes to tera

        ARGS:
        df - dataframe
        q - string - query
        table_name - string

        example format:
        q = Insert into d_digital_data.blabla values (?, ?, ?, ?)
        table_name = d_digital_data.blabla

        Return:
        nan
        """
        self.uploade_how_many_rows_we_want(self.df, self.q, self.table_name)
        if len(self.l)==0:
            print("done")
        else:
            # union all tables
            with t.connect('{"host":"tdprd","logmech":"krb5"}') as con:
                with con.cursor () as cur:
                    q_union = "sel * from {0}".format(self.l[0])
                    for item in self.l[1:]:
                        q_union +=" union all sel * from {0}".format(item)

                    q_final = """insert into {0}
                    {1}
                    """.format(self.table_name, q_union)
                    cur.execute(q_final)
                    #print("l: ", self.l)
                    for item in list(set(self.l)):
                        cur.execute("drop table {0}".format(item))
                    print("num_of_tables: " + str(self.num))
                    print('done')

    def uploade_how_many_rows_we_want(self, df, q, table_name):
        """
        A recursion that will divide our data into several parts and upload them to tera.

        ARGS:
        df - dataframe
        q - string - query
        table_name - string
        l - list - keep empty

        example format:
        q = Insert into d_digital_data.blabla values (?, ?, ?, ?)
        table_name = d_digital_data.blabla

        Return:
        nan
        """
        try:
            if len(df) > 300000 or df.memory_usage(deep=True).sum() > self.memory:
                raise Exception("batch request")
            try:
                self.insert(q, df)
            except Exception as ex:
                if 'string contains an untranslatable character' in str(ex):
                    for i in np.where(df.dtypes != np.float)[0]:
                        df['drop'] = df[df.columns[i]].apply(lambda x: self.is_ascii(x))
                        l_tmp = (df['drop'][df['drop']].index)
                        if len(l_tmp) > 0:
                            print("rows remove: " + str(list(l_tmp)))
                            self.bar.update(len(l_tmp))
                        df.drop(l_tmp, inplace=True)
                        df.drop('drop', axis=1, inplace=True)
                elif 'batch request' in str(ex) or 'LAN message' in str(ex):
                    raise Exception("batch request")
                else:
                    with t.connect('{"host":"tdprd","logmech":"krb5"}') as con:
                        with con.cursor () as cur:
                            for item in list(set(self.l)):
                                cur.execute("drop table {0}".format(item))
                    print('error')
                    print(ex)
                    raise error
            self.rows += len(df)
            self.bar.update(len(df))


        except Exception as ex:
            if "batch request" in str(ex):
                with t.connect('{"host":"tdprd","logmech":"krb5"}') as con:
                    with con.cursor () as cur:
                        # create new tables in tera
                        if table_name != self.table_name:
                            cur.execute("drop table {0}".format(table_name))
                            self.l.remove(table_name)

                        if table_name != self.table_name:
                            tmp_num = len(str(self.num))
                            table_name1 = table_name[:-tmp_num] + str(self.num)
                            self.num += 1
                            table_name2 = table_name[:-tmp_num] + str(self.num)
                            self.num += 1
                        else:
                            table_name1 = table_name + str(self.num)
                            self.num += 1
                            table_name2 = table_name + str(self.num)
                            self.num += 1
                        create_statment1 = self.create_statment.replace(self.table_name, table_name1)
                        create_statment2 = self.create_statment.replace(self.table_name, table_name2)
                        cur.execute(create_statment1)
                        cur.execute(create_statment2)

                        # usally, tera upload some of the data before crashing.
                        # we dont want duplicates.

                        # split the data to 2 dataframes
                        len_data = math.ceil(len(df)/2)
                        df1 = df.iloc[:len_data]
                        df2 = df.iloc[len_data:]

                        # replace query
                        q1 = q.replace(table_name, table_name1)
                        q2 = q.replace(table_name, table_name2)

                        self.l.append(table_name1)
                        self.uploade_how_many_rows_we_want(df1, q1, table_name1)
                        self.l.append(table_name2)
                        self.uploade_how_many_rows_we_want(df2, q2, table_name2)


            else:
                print (ex)
                with t.connect('{"host":"tdprd","logmech":"krb5"}') as con:
                    with con.cursor () as cur:
                        for item in list(set(self.l)):
                            cur.execute("drop table {0}".format(item))
                raise error
