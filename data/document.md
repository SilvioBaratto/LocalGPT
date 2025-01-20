Version 1.1

December 2022

Forward engineering methods in the context of BIRD

Content
0.

Version control

1.

1.1

2.

2.1

2.1.1

2.1.2

2.2

2.2.1

2.2.2

2.2.3

Introduction

Remark on normalisation & denormalisation

Forward engineering methods

General considerations regarding forward engineering

Treatment of optionality for enumerated and non-enumerated attributes / columns

Conserving referential integrity (via validation rules & Null Explanatory Values (NEVs))

Merging entity types into tables

Merging entity types into a supertype / subtype

Merging entity types connected via relationship types

Merging tables with equal surrogate keys

2

2

3

3

4

4

4

7

7

14

21

Page 1 of 21

0.  Version control

Version

Date

Comments

1.0

1.1

08/11/2021

Initial draft

16/12/2022

Incorporation of comments and suggestions for improvement

provided by members of the Work Stream on Prototyping

(formerly known as Work Stream on Testing) and of the

temporary BIRD subgroup on logical data model and input layer

(LDM/IL) review.

1.

Introduction

The information that is relevant for fulfilling the reporting requirements covered by the BIRD documentation

is described in the BIRD Logical Data Model (LDM). This LDM is a highly normalised model that describes

the logic of the business domain (i.e., the information that is relevant for fulfilling the reporting requirements),

it does not take into account any implementation specific considerations.

The BIRD Input Layer (IL) is intended to act as an implementation model based on the IL design principles.

This  IL  is  derived  from  the  LDM  via  so  called  forward  engineering  methods  which  we  define  as  a

combination of denormalisation and additional (validation) rules to ensure “semantic equivalence” between

the  LDM  and  the  IL.  This  document’s  purpose  is  to  describe  these  forward  engineering  methods,  their

behaviour and implications1. It also tries to describe the validation rules2 that are necessary to ensure that

the data stored in the IL is consistent with the definition of the data structures in the LDM.

To support the reader in distinguishing between logical and technical model artefacts we will use the terms

entity type and attribute when referring to the LDM and table and column for the implementation model (e.g.

IL). We will use the term domain when referring to both models.

Please note that the examples given in this document were adapted for educational purpose and do not

represent the exact state of the LDM or IL.

1 Forward engineering does not include any form of aggregation. Aggregation of data is an aspect that needs to be

managed/handled within transformation (of the data from the input to the output).

2 Validation rules are currently under development and will be implemented in the future.

Page 2 of 21

1.1  Remark on normalisation & denormalisation

Before  describing  the  forward  engineering  methods  which  is  a  denormalisation  process,  we  believe  it

important to define what we mean by denormalisation because “for a practice that’s so widely advocated,

there seems to be considerable confusion over what denormalisation actually consists of.”3. Fully aligned

with the author of this quote we define denormalisation as the inverse of normalisation and therefore the

process to decrease a data structure’s normal form to a lower normal form, e.g., from 3rd normal form to

2nd normal form. In order to avoid losing information the documentation of validation rules for the new data

structure resulting from denormalisation is required.

As regards the question when a model is sufficiently denormalised we would like to underline that “With

normalisation, where there are clear logical reasons for continuing the process until we reach the highest

possible normal form. Do we then conclude that with denormalisation we should proceed until we reach the

lowest possible normal form?  Surely not; yet there  are no logical criteria for deciding  exactly where the

process should stop. In choosing to denormalise, in other words, we’ve backed from a position that does

at least have some solid science and logical theory behind it, and replaced it by one that’s purely pragmatic

in nature…”4.

2.

Forward engineering methods

This  section  describes  the  different  forward  engineering  methods.  Each  method  is  introduced  by  a

description of the operation itself, i.e., what operation is to-be-applied onto the entity types of the LDM to

forward engineer tables of the IL, an example and an analysis of the implied consequences for applying

this  forward  engineering  method.  The  first  subsection  of  this  chapter  describes  general  aspects  about

forward engineering which are relevant for all following sections.

Please  note  that  we  have  amended  the  existing  LDM  by  adding  additional  attributes  or  changing  the

optionality  of  attributes  to  cover  relevant  cases  regarding  forward  engineering  from  a  conceptual

perspective. Wherever there were adjustments made to the LDM we will highlight it in the respective section

or example accordingly.

3 See Database Design and Relational Theory, section 8. Denormalization, subsection What does Denormalization

Mean? by C.J. Date

4 See Database Design and Relational Theory, section 8. Denormalization, subsection What does Denormalization

Mean? by C.J. Date

Page 3 of 21

2.1

General considerations regarding forward engineering

2.1.1  Treatment of optionality for enumerated and non-enumerated attributes / columns

Firstly, we would like to highlight the different treatment of enumerated and non-enumerated attributes in

the LDM and columns in the IL with respect to their representation of optionality, i.e., if these attributes /

columns are considered as optional or not.

Enumerated attributes / columns are attributes / columns where only a defined set of values is allowed, an

example would be the Address country which allows only countries listed in ISO 3166. Non-enumerated

attributes / columns on the other hand are attributes / columns where the allowed values are not specified

via a set of specific values but defined more broadly, e.g., the Balance sheet total which may be any numeric

value.

Optionality of an attribute / column specifies if this attribute / column is optional or mandatory.

For  non-enumerated  attributes  /  columns  optionality  is  specified  on  the  attribute  /  column  itself,  i.e.  the

attribute / column in the entity type / table is defined to be optional or mandatory. For example, mandatory

attributes in the LDM are indicated via a red star next to the attribute itself as illustrated in the following

picture.

Figure 1: Entity Organisation having mandatory (red star) and non-mandatory Attributes

For enumerated attributes / column optionality is specified differently. It is specified via a specific value, i.e.

Not applicable, and enumerated attributes / columns are always defined as mandatory (always have a red

star next to the attribute itself). Consequently, if the allowed values for an enumerated  attribute / column

comprises the value Not applicable this attribute / column is defined as optional. Conversely, if the allowed

values do not comprise the value Not applicable, this attribute / column is defined to be mandatory.

2.1.2  Conserving referential integrity (via validation rules & Null Explanatory Values (NEVs))

The second aspect that we would like to highlight concerns the conservation of referential integrity, which

may be formulated as: the forward engineering methods that are applied to the LDM should conserve the

rules which are specified in the LDM itself.

Page 4 of 21

An  example  of  such  a  rule  is  the  attribute  International  organisation  code  which  is  only  applicable  to

International organisations, like the International Monetary Fund or the European Central Bank. For all other

types  of  Organisations,  like  Credit  institutions  or  Non-financial  institutions  the  attribute  International

organisation code does not exist. If we put different types of Organisations into one table which comprises

the  column  International  organisation  code  we  need  to  ensure  that  only  for  Organisations  which  are

International organisations this column is populated with an allowed value, while for Organisations which

are not International organisations this column must take the value Not applicable. If we wouldn’t conserve

this  referential  integrity  constraint  the  result  IL  would  allow  to  represent  Organisations  which  are  not

International organisations having an International organisation code, which is clearly a data quality issue

which may result in incorrect aggregation and therefore incorrect output figures.

2.1.2.1. Example

The following example will give the reader an overview of the type of validations that are required to ensure

referential integrity. It is also the basis for the following section dedicated to Null Explanatory Values (NEVs)

& validation rules.

Let’s assume we have two entity types that we want to merge into one table holding the following data:

Figure 2: Content of the entity type Organisation

Figure 3: Content of the entity type Natural person

Merging this data into one data result in the following Table:

Page 5 of 21

Legal person identifierOrganisation nameBalance sheet totalmandatorymandatoryoptional{String}{String}{Integer}Apple Inc.Apple Inc.57,000,000,000Grüne ErdeGrüne ErdeNULLGoldman Sachs Group, Inc.Goldman Sachs Group, Inc.12,000,000,000,000Other companyOther companyNULL………OrganisationLegal person identifierFirst nameLast namemandatorymandatorymandatory{String}{String}{String}Marie CurieMarieCurieAlbert EinsteinAlbertEinsteinBernhard RiemannBernhardRiemann………Natural person

Figure 4: Resulting Organisation & Natural person table

Which  requires  the  following  validation  rules  to  ensure  consistency  with  the  data  illustrated  in  Figure  2:

Content of the entity type Organisation and Figure 3: Content of the entity type Natural person:

•

if Legal person type is Organisation

o

o

the following columns must be NULL: First name, Last name

the following columns must not be NULL: Organisation name

•

if Legal person type is Natural person

o

o

the following columns must be NULL: Organisation name, Balance sheet total

the following columns must not be NULL: First name, Last name

Please note that without the validation rules we cannot distinguish between NULL values in the  column

Balance sheet total, i.e., we don’t know if it is NULL because the concept does not apply to the subtype

which is the case for Natural person or NULL because the concept is optional for the subtype which is the

case for Organisations.

2.1.2.2. Null Explanatory Values (NEVs) & validation rules

As illustrated in the previous example, it is possible to describe necessary validation rules without so called

Null  Explanatory  Values  (NEVs),  however  information,  specifically  about  the  optionality  of  attributes

Page 6 of 21

Legal person identifierLegal person typeOrganisation nameBalance sheet totalFirst nameLast namemandatorymandatoryoptionaloptionaloptionaloptional{String}{Organisation, Natural person}{String}{Integer}{String}{String}Apple Inc.OrganisationApple Inc.57,000,000,000NULLNULLGrüne ErdeOrganisationGrüne ErdeNULLNULLNULLGoldman Sachs Group, Inc.OrganisationGoldman Sachs Group, Inc.12,000,000,000,000NULLNULLOther companyOrganisationOther companyNULLNULLNULLMarie CurieNatural personNULLNULLMarieCurieAlbert EinsteinNatural personNULLNULLAlbertEinsteinBernhard RiemannNatural personNULLNULLBernhardRiemann………………Organisation & Natural person tableLegal person identifierLegal person typeOrganisation nameNull explanatory value (Organisation name)Balance sheet totalNull explanatory value (Balance sheet total)First nameNull explanatory value (First name)Last nameNull explanatory value (Last name)mandatorymandatoryoptionalmandatoryoptionalmandatoryoptionalmandatoryoptionalmandatory{String}{Organisation, Natural person}{String}{Not NULL because mandatory for this type, NULL because the concept does not apply for this type}{Integer}{NULL or not NULL because optional for this type, NULL because the concept does not apply for this type}{String}{Not NULL because mandatory for this type, NULL because the concept does not apply for this type}{String}{Not NULL because mandatory for this type, NULL because the concept does not apply for this type}Apple Inc.OrganisationApple Inc.Not NULL because mandatory for this type57,000,000,000NULL or not NULL because optional for this typeNULLNULL because the concept does not apply for this typeNULLNULL because the concept does not apply for this typeGrüne ErdeOrganisationGrüne ErdeNot NULL because mandatory for this typeNULLNULL or not NULL because optional for this typeNULLNULL because the concept does not apply for this typeNULLNULL because the concept does not apply for this typeGoldman Sachs Group, Inc.OrganisationGoldman Sachs Group, Inc.Not NULL because mandatory for this type12,000,000,000,000NULL or not NULL because optional for this typeNULLNULL because the concept does not apply for this typeNULLNULL because the concept does not apply for this typeOther companyOrganisationOther companyNot NULL because mandatory for this typeNULLNULL or not NULL because optional for this typeNULLNULL because the concept does not apply for this typeNULLNULL because the concept does not apply for this typeMarie CurieNatural personNULLNULL because the concept does not apply for this typeNULLNULL because the concept does not apply for this typeMarieNot NULL because mandatory for this typeCurieNot NULL because mandatory for this typeAlbert EinsteinNatural personNULLNULL because the concept does not apply for this typeNULLNULL because the concept does not apply for this typeAlbertNot NULL because mandatory for this typeEinsteinNot NULL because mandatory for this typeBernhard RiemannNatural personNULLNULL because the concept does not apply for this typeNULLNULL because the concept does not apply for this typeBernhardNot NULL because mandatory for this typeRiemannNot NULL because mandatory for this type…………………………Organisation & Natural person table

associated with certain subtypes is only implicitly comprised in the validation rules and rather difficult to

extract, i.e. translating data from the IL to the LDM is not feasible with such an approach. Additional NEVs

associated with specific columns would make some of the information more explicit and therefore provide

additional context as illustrated in the following figure:

Figure 5: Resulting Organisation & Natural person table including Null Explanatory Values (NEVs)

Because of the additional information provided in the Null explanatory value (Balance sheet total) we made

it explicit that for Organisations it is NULL or not NULL because optional for this type and for Natural persons

the value must be NULL because the concept does not apply for this type (see highlighted in green).

2.2

Merging entity types into tables

2.2.1  Merging entity types into a supertype / subtype

2.2.1.1. Description of the forward engineering method

This method is used to merge multiple entity types which are connected via subtyping into one of their

supertypes. The resulting table comprises the distinct union of all attributes of the merged subtypes as

columns, the allowed values of the columns of this table result from the union of allowed values of the

attributes. If an attribute is only present in some subtypes but not in others it becomes optional in the

resulting table.

2.2.1.2. Legal person example

To illustrate the implications of this forward engineering method we will introduce it based on the following

example, which was extracted from the LDM and slightly modified to cover additional use cases5.

5 Here is a list of the amendments we’ve applied for this example: (1) moved the Institutional sector to the subtype

level, (2) added Number of employees, Country and Balance sheet on the Organisation level, (3) added Gender,
Country, Nationality, Social security number, Number of employees on the Natural person level.

Page 7 of 21

On  the  logical  level,  we  distinguish  between  two  (sub-)types  of  Legal  persons,  i.e.  Organisations  and

Natural persons, as illustrated in the following picture.

Figure 6: A Legal person is either an Organisation or a Natural person

Please note that this example comprises, among other aspects:

•  Enumerated and non-enumerated attributes which are present in some subtypes but not in others,

optional and mandatory, e.g. Organisation name, Balance sheet total, Country

•  Enumerated  attributes  which  are  present  in  all  subtypes,  mandatory  in  all  subtypes,  e.g.

Institutional sector

•  Non-Enumerated  attributes  which  are  present  in  all  subtypes,  mandatory  in  some,  optional  in

others, e.g. Number of employees

Applying forward engineering methods, specifically Merging entity types into a supertype / subtype, we will

end up with one resulting table and additional validation rules.

For  educational  purposes  we  will  explain  the  required  validation  rules  based  on  “data”,  therefore  let’s

assume the entity types are populated as following. The content of the entity type Legal person may hold

the following data:

Page 8 of 21

Legal person identifierLegal person typemandatorymandatory{String}{Organisation, Natural person}Apple Inc.OrganisationGrüne ErdeOrganisationGoldman Sachs Group, Inc.OrganisationOther companyOrganisationMarie CurieNatural personAlbert EinsteinNatural personBernhard RiemannNatural person……Legal person

Figure 7: Content of the entity type Legal person

Please  note  that  green  highlighted  columns  indicate  components  of  the  primary  key,  in  this  example  it

indicates that the value of the column Legal person identifier must be unique. The entity type Organisation

may be populated as following:

And, the entity type Natural person may have the following content:

Figure 8: Content of the entity type Organisation

Figure 9: Content of the entity type Natural person

Wrapping up these entity types will result in one table comprising all the columns illustrated in figures above,

we may illustrate it as following:

Figure 10: Legal person table

Page 9 of 21

Legal person identifierOrganisation nameLegal entity identifier (LEI)Institutional sectorNumber of employeesLegal formCountryBalance sheet totalmandatorymandatorymandatorymandatorymandatorymandatorymandatoryoptional{String}{String}{String}{Institutional sectors applicable to Companies}{Integer}{Legal form codes including Not applicable}{ISO Countries including Not applicable}{Integer}Apple Inc.Apple Inc.Apple LEINon-financial corporations147000Stock companyUnited States of America57,000,000,000Grüne ErdeGrüne ErdeGrüne Erde LEINon-financial corporations500LimitedAustriaNULLGoldman Sachs Group, Inc.Goldman Sachs Group, Inc.Goldman Sachs LEICredit institution40500Stock companyUnited States of America12,000,000,000,000Other companyOther companyOther company LEINon-financial corporations3LimitedNot applicableNULL……………………OrganisationLegal person identifierFirst nameLast nameGenderInstitutional sectorCountryNationalitySocial security numberNumber of employeesmandatorymandatorymandatorymandatorymandatorymandatorymandatoryoptionaloptional{String}{String}{String}{Gender}{Institutional sectors applicable to Natural persons}{ISO Countries}{ISO Countries}{String}{Integer}Marie CurieMarieCurieFemaleHouseholdsFrancePolishNULL2Albert EinsteinAlbertEinsteinMaleHouseholdsUnited States of AmericaGermanssnAlbertEinsteinNULLBernhard RiemannBernhardRiemannMaleHouseholdsGermanyGermanNULLNULL………………………Natural person

The associated data compatible with the data illustrated in Figure 7: Content of the entity type Legal person

to Figure 9: Content of the entity type Natural person is as following:

Figure 11: Content of the Legal person table

Please note that default values are illustrated in red, e.g. the value NULL in the column Organisation name

for Marie Curie. The associated validation rules may be formulated as following:

•

If the Legal person type is Organisation

o  The following columns must be NULL: First name, Last name, Social security number

o  The following columns must not be NULL: Organisation name, Legal entity identifier (LEI),

Number of employees

o  The following columns must take the value Not applicable: Gender, Nationality

o  The following columns must take specific values:

▪  The  column  Institutional  sector  must  take  a  value  from  {Institutional  sectors

applicable to Companies}

•

If the Legal person type is Natural person

o  The  following  columns  must  be  NULL:  Organisation  name,  Legal  entity  identifier  (LEI),

Balance sheet total

o  The following columns must not be NULL: First name, Last name

o  The following columns must take the value Not applicable: Legal form

o  The following columns must take specific values:

▪  The  column  Institutional  sector  must  take  a  value  from  {Institutional  sectors

applicable to Natural persons}

Page 10 of 21

Legal person identifierLegal person typeOrganisation nameLegal entity identifier (LEI)Institutional sectorNumber of employeesLegal formCountryBalance sheet totalFirst nameLast nameGenderNationalitySocial security numbermandatorymandatoryoptionaloptionalmandatoryoptionalmandatorymandatoryoptionaloptionaloptionalmandatorymandatoryoptional{String}{Organisation, Natural person}{String}{String}{Institutional sectors applicable to Companies or Natural persons}{Integer}{Legal form codes including Not applicable}{ISO Countries including Not applicable}{Integer}{String}{String}{Gender including Not applicable}{ISO Countries including Not applicable}{String}Apple Inc.OrganisationApple Inc.Apple LEINon-financial corporations147000Stock companyUnited States of America57,000,000,000NULLNULLNot applicableNot applicableNULLGrüne ErdeOrganisationGrüne ErdeGrüne Erde LEINon-financial corporations500LimitedAustriaNULLNULLNULLNot applicableNot applicableNULLGoldman Sachs Group, Inc.OrganisationGoldman Sachs Group, Inc.Goldman Sachs LEICredit institution40500Stock companyUnited States of America12,000,000,000,000NULLNULLNot applicableNot applicableNULLOther companyOrganisationOther companyOther company LEINon-financial corporations3LimitedNot applicableNULLNULLNULLNot applicableNot applicableNULLMarie CurieNatural personNULLNULLHouseholds2Not applicableFranceNULLMarieCurieFemalePolishNULLAlbert EinsteinNatural personNULLNULLHouseholdsNULLNot applicableUnited States of AmericaNULLAlbertEinsteinMaleGermanssnAlbertEinsteinBernhard RiemannNatural personNULLNULLHouseholdsNULLNot applicableGermanyNULLBernhardRiemannMaleGermanNULL……………………………………Legal person Table

▪  The column Country must take a value from {ISO Countries}

▪  The column Gender must take a value from {Gender}

▪  The column Nationality must take a value from {ISO Countries}

We  would  like  to  highlight  that  we  are  not  able  to  distinguish  between  NULL  because  an  attribute  was

optional for a specific subtype and NULL because the attribute does not apply for a specific subtype. For

example, we are not able to distinguish between the NULL values for the column Balance sheet total for

the records of Organisation Grüne Erde or Marie Curie, where the latter is NULL because the concept (of

Balance sheet total) does not apply for a specific subtype (i.e. for Natural persons) and the former is NULL

because the concept is optional for a specific subtype. In theory this information may be extracted from the

validation rule stating that the Column Balance sheet total must be NULL for Natural persons, however this

requires  the  creation  of  logic  from  statements  which  is  a  rather  difficult  task  and  consequently  not

recommended.

2.2.1.3. Subtypes, merging & Relationships

Subtypes may be connected to other entity types via relationship types. When a subtype is merged into its

supertype  these  relationship  types  need  to  be  managed  as  well,  otherwise  we  would  lose  them  and

therefore our forward engineered model would be incomplete. An example of such a  relationship type is

the relationship type between an Organisation and its Organisational units, i.e. an Organisation has zero,

one-or-many Organisational units. In more practical terms, a Credit institution may have multiple Branches.

The situation, as described in the LDM, is illustrated in the following figure.

Figure 12: Relationship type between Institutional unit of foreign branches and Organisational unit and their hierarchy

Page 11 of 21

When merging the involved entity types into their respective supertypes, relationship types applicable only

to  subtypes  vanish  because  they  cannot  be  expressed  via  SQL  foreign  key  constraints6  anymore.

Consequently,  they  cannot  be  established  on  the  database  level  directly  but  have  to  be  validated  via

validation rules. The following figure illustrates the resulting situation:

Figure 13: Party & Group table

The following validation rules complete the picture, i.e., ensure that the columns establishing the connection

between the tables can only be populated according to the description in the LDM:

•  As regards the Party table

o  The  Institutional  unit  of  foreign  branches  Group  identifier  must  be  NULL  for  all  Parties

where the Organisational unit type is different to Branch

o

If  the  Institutional  unit  of  foreign  branches  Group  identifier  is  not  NULL,  the  following

conditions must hold:

▪  The Organisational unit type must be Branch

▪  The  Institutional  unit  of  foreign  branches  Group  identifier  must  refer  to  a  Group

where the Internal group type is Institutional unit of foreign branches

2.2.1.4. Disjoint subtyping

Disjoint subtyping describes a situation where a supertype is split into two different disjoint classifications.

In the LDM this is the case for Securities in the form of debt or direct ownership, where one type of subtyping

is by classification into Debt security, Equity security and Fund security while the other type of subtyping is

by type of identifier into ISIN securities and Non-ISIN securities.

6 For additional information regarding foreign key constraints, please see

https://www.w3schools.com/sql/sql_foreignkey.asp

Page 12 of 21

Figure 14: Disjoint subtyping of Security (in the form of debt or direct ownership) by product (Debt security and Equity

or Fund security) and identifier (ISIN vs. Non-ISIN)

As regards necessary validation rules to ensure consistency with the LDM the only real difference is that

each type of subtyping will result in a separate set of validation rules. In our specific example mentioned

above this would result in validation rules for subtyping by classification and validation rules for subtyping

by type of identifier. Other than that, the resulting validation rules are similar to the validation rules described

in the previous section, see Legal person example.

2.2.1.5. Implications

As discussed in the previous sections the application of this forward engineering method has implications

if consistency with the LDM must be ensured.

As regards the columns of the resulting table with respect to the attributes they originate from:

•  For non-enumerated columns it needs to be ensured that NULL values are allowed / not allowed

according to the specification in the originating  entity type, e.g., if a non-enumerated attribute  is

mandatorily present for a specific subtype, the corresponding column must be different than NULL

•  For  enumerated  columns  it  needs  to  be  ensured  that  the  value  is  Not  applicable  by  default

according  to  the  specification  in  the  merged  entity  types,  e.g.,  if  an  enumerated  attribute  is  not

present  in  all  subtypes  that  are  to-be-merged,  the  resulting  column  must  take  the  value  Not

applicable for those subtypes

•  For  enumerated  columns  it  needs  to  be  ensured  that  the  allowed  values  correspond  to  the

specification in the LDM with respect to the specific subtypes, e.g., if a mandatory, enumerated

attribute allowed only ISO country codes the corresponding column must only allow these values

for the specific subtype as well

•  For  columns  establishing  a  connection  with  other  tables  resulting  from  relationship  types  of

subtypes, it needs to be ensured that the allowed value refers to the allowed subtypes only

Another implication of merging entity types with different attributes is that the resulting table will comprise

mainly optional columns (or columns where the value Not applicable is valid).

Page 13 of 21

2.2.2  Merging entity types connected via relationship types

2.2.2.1. Description of the forward engineering method

Merging entity types connected via relationship types  is a forward engineering method where two  entity

types that are connected via a  relationship type  are  merged into one  table. This method is intended for

identifying relationship types only. The cardinality of the relationship type may be of type one-to-one or one-

to-many which are either optional or mandatory. The resulting table’s primary key will be equal to the largest

primary key of the involved entity types, e.g., if a one-to-many relationship type is involved the resulting

table’s primary key will be equal to the entity type with the many cardinality.

2.2.2.2. Merging one-to-one, mandatory entity types

Since one-to-one, mandatory relationship types represent an arbitrary split of an entity type into two entity

types, at least from a logical perspective, the resulting table’s columns will be the result of the union of all

attributes of the involved entity types. The optionality of the columns doesn’t change.

In the LDM such a one-to-one relationship type is established via Party and Party derived data where the

later  entity  type  comprises  derived  data,  e.g.,  the  Institutional  sector  according  to  EBA  ITS.  The  LDM

situation may be illustrated as following:

While the resulting table may be illustrated like this:

Figure 15: Party & Party derived data

Page 14 of 21

Figure 16: Resulting Party table (indicated)

2.2.2.3. Merging one-to-one, optional entity types (“de-facto subtypes”)

When merging de-facto subtypes, all attributes of the optional entity type become optional. Because of the

lack of discriminators for de-facto subtypes in the LDM it is not possible to distinguish between optional and

mandatory  columns  in  the  resulting  Table  directly.  Consequently,  validating  data  of  the  IL  can  only  be

achieved indirectly, i.e., if one of the columns resulting from a mandatory attribute is different to NULL / Not

applicable all other columns resulting from mandatory attributes must be different to NULL / Not applicable.

2.2.2.4. Merging one-to-many, mandatory

Merging entity types which are connected via a one-to-many, mandatory relationship type creates a table

having the primary key of the entity type, which is at the many end of the relationship type, i.e., the one with

more attributes contributing to the primary key. Merging such entity types requires validation rules to ensure

that duplicated values are consistent. As an example, we look at the situation of Protection items and their

Protection values in the LDM.

Figure 17: Protection item has one-or-many Protection value(s)

A  Protection  item  has  one-or-many  Protection  values,  while  a  Protection  value  always  belongs  to  a

Protection item. The resulting table after merging these entities looks as following:

Page 15 of 21

Figure 18: Resulting Protection item & Protection value table

We also need to ensure that the same Protection item always has equal values in the attributes present in

the entity type Protection item, otherwise referential integrity would be violated, therefore:

•  For each value of the attribute Protection item identifier the values of the following attributes need

to take the same value: Protection item type, Original protection value, Date of original protection

value

2.2.2.5. Merging one-to-many, optional

The situation for entity types connected via a one-to-many, optional relationship type is a little different than

the previous situation. The main reason is that with such a relationship type the entity type at the many end

of the relationship type is optional. Therefore, when merging such entity types, we need to ensure that the

primary key (constraint) is not violated.

For educational purposes we quote the definition of the primary key according to w3schools: “The primary

key constraint  uniquely  identifies  each record in a table. Primary keys  must contain unique values,  and

cannot contain NULL values.” 7 The important aspect that we need to consider in this context is that the

values (of the primary key) must not be NULL.

2.2.2.5.1. Entity types on the many side of the relationship with non-enumerated attributes being

components of the primary key

Clearly, if we merge two entity types which are related via a one-to-many, optional relationship type, where

the  primary  key  of  the  entity  type  on  the  many  side  of  the  relationship  type  comprises  non-enumerated

attributes  which  are  not  present  in  the  other  entity  type  we  will  violate  this  definition  and  therefore  the

resulting table will not be a valid table in a relational data model. To illustrate the content of the previous

paragraph please consider the following situation:

7 See https://www.w3schools.com/sql/sql_primarykey.ASP

Page 16 of 21

Figure 19: Debt security is involved in zero, one-or-many Debt security position(s)

A Debt security may be held by multiple Investors while an Investor may invest in multiple Debt securities.

We call this combination of a Debt security and an Investor a Debt security position. Please note that not

every Debt security is involved in a Debt security position, i.e., the relationship type between Debt security

and Debt security position is optional. To illustrate the problem, let’s consider the following example: in the

entity type Debt security we register the following security information:

Figure 20: Registered debt securities

While  the  Austrian  and  the  German  bond  are  held  by  Parties,  the  Company  bond  is  not,  therefore  the

content of the entity type Debt security position might be illustrated as following:

Figure 21: Content of the entity type Debt security position

Page 17 of 21

Security identifierCurrency…{String}{Euro, United States Dollar,…}…Austrian bondEuro…German bondEuro…Company bondUnited States Dollar…………Debt securitySecurity identifierInvestor Party identifierOutstanding nominal  amount{String}{String}{Integer}Austrian BondSome Austrian bank13Austrian BondSome German bank19German BondSome Italian bank23………Debt security position

If we’d merge the two entity types the resulting table’s primary key would be equal to the primary key of the

Debt security position entity type. The resulting data for this example would look as following:

Figure 22: Content of the Debt security & Debt security position table

Since the Company bond is not held by any Investor, the Attribute Investor Party identifier would be NULL

(highlighted in red). This, however, would violate the definition of the primary key and therefore merging

entity types connected via a one-to-many, optional relationship type in case the entity type on the many

side of the relationship type has a non-enumerated attribute, that is not part of the other entity type’s primary

key, as a component of the primary key is not possible.

To ensure that duplicated values are consistent we also need to implement additional validation rules, e.g.,

to ensure that the same value of the attribute Security identifier has the same value in the attribute Currency.

2.2.2.5.2. Entity types on the many side of the relationship type with enumerated attributes being

components of the primary key

The situation is slightly different if the attributes contributing to the primary key of the  entity type (on the

many  side  of  the  relationship  type),  that  are  not  comprised  in  the  other  entity  type’s  primary  key,  are

enumerated.  In  this  case  someone  might  argue  that  the  value  Not  applicable  is  different  to  NULL  and

therefore a valid value for absent data. Consequently, following this argumentation, we would not violate

the definition of the primary key. Please note that this argument is debatable because indeed the value Not

applicable has the same meaning as NULL for non-enumerated attributes.

Page 18 of 21

Security identifierInvestor Party identifierCurrencyOutstanding nominal  amount{String}{String}{Euro, United States Dollar,…}{Integer}Austrian BondSome Austrian bankEuro13Austrian BondSome German bankEuro19German BondSome Italian bankEuro23Company bondNULLUnited States DollarNULL…………Debt security & Debt security position Table

This constellation occurs in multiple locations in the LDM, for example when applying the role concept to

specific entity types. To illustrate the indicated situation and the implications of the application of this forward

engineering method in more detail let’s look at the role concept applied to Parties.

Figure 23: A Party acts in zero, one-or-many Party role(s)

Via this optional, one-to-many relationship type between Party and Party role a Party can act in multiple

Party roles, e.g. Debtor, Creditor, Investor, at the same time. Like the previous example we will analyse

some “data”, e.g.

Figure 24: Content of the entity type Party

Some of these Parties may act in specific roles, e.g., the Austrian bank may act in the Party roles Creditor

and Investor, the German bank may act in the Party role Investor. Please note that Some Company does

not act in any Party role.

Page 19 of 21

Party identifierParty role type{String}{Debtor, Creditor, Austrian bankCreditorAustrian bankInvestorGerman bankInvestor……Party roleParty identifierCountry…{String}{Austria, Germany,…}…Austrian bankAustria…German bankGermany…Some CompanyAustria…………Party

Figure 25: Content of the entity type Party role

If we would merge these two entity types, the resulting table’s primary key is equal to the primary key of

the entity type Party role. For the resulting table, the data indicated in Figure 24: Content of the entity type

Party and Figure 25: Content of the entity type Party role would look as following:

Figure 26: Resulting Party & Party role table

Because Some Company does not act in any Party role, we would use the value Not applicable as a default

value.

As regards validation rules, similar to the previous example we will need to ensure that every value of Party

identifier has consistent values for columns arising solely form the entity type Party, i.e. ensure consistency

of duplicated values.

2.2.2.6. Implications

The main restriction when applying this forward engineering method is that entity types which are connected

via one-to-many, optional relationship types, where the entity type on the many side of the relationship type

has non-enumerated attributes (which are not present in the other entity type) as components of the primary

key, cannot be merged. In case of enumerated attributes contributing to the primary key we may apply this

forward engineering method, however the difference between NULL and Not applicable is debateable.

Another important remark from the previous sections is that the resulting tables from entity types connected

via one-to-one, optional relationship types (“de-facto subtypes”) can only be validated indirectly against the

LDM.

Lastly, when applying this method to the entity types connected via one-to-many relationship types we need

to specify validation rules to ensure that duplicated values are consistent according to their original primary

keys.

Page 20 of 21

Party identifierParty role typeCountry…{String}{Debtor, Creditor, Investor,…}{Austria, Germany,…}…Austrian bankCreditorAustria…Austrian bankInvestorAustria…German bankInvestorGermany…Some CompanyNot applicableAustria……………Party & Party role Table

2.2.3  Merging tables with equal surrogate keys

2.2.3.1. Description of the forward engineering method

In  some  situations,  we  may  want  to  merge  entity  types  having  different  primary  keys.  Because  of  the

different primary keys we cannot simply merge these  entity types as described in section Merging entity

types into a supertype / subtype but we would have to create a matching primary key first. We refer to this

operation as the Creation of surrogate keys. It goes without saying that we need additional validation rules

to ensure referential integrity if we create such a new surrogate key. After different  entity types have the

same surrogate key we may want to merge them similar to the situation described in Merging entity types

into a supertype / subtype.

2.2.3.2. Creation of surrogate keys

In practical terms, the creation of a surrogate key for an entity type involves the following steps:

•  Definition of a new surrogate key, i.e. adding an attribute / column with unique values

•  Removing the previous primary key (in terms of key constraints)

•  Specifying the new surrogate key to be the primary key

•  Specifying validation rules ensuring consistency as regards the previous primary key

2.2.3.3. Merging tables having equal surrogate keys

After creating surrogate keys for different entity types, we may merge these entity types. One prerequisite

for  merging  entity  types  having  the  same  surrogate  key  is  that  the  values  of  the  surrogate  keys  of  the

entities  do  not  overlap.  If  these  values  would  overlap,  we  cannot  distinguish  between  the  instances

anymore. The required validation rules for this method are similar to the validation rules described  in the

Legal person example.

2.2.3.4. Implications

The main constraint when applying this forward engineering method is to ensure that the surrogate keys of

the different entity types to-be-merged must have non-overlapping values. However, this is a data related

topic which can only described from a meta data perspective like the BIRD documentation.

Another  consideration  in  this  context  that  should  be  taken  into  account  is  the  data  lineage  capabilities

between the LDM and the IL, i.e. how “easy” it is to link the entity types of the LDM to the table of the IL or

vice-versa. Applying this forward engineering method on too many entity types of the LDM to merge them

into one table of the IL will make it more difficult to understand how the tables are related (in detail) with the

entity types.

Page 21 of 21


