from typing import List, Union

from langchain.prompts.prompt import PromptTemplate
from langchain.chains import AnalyzeDocumentChain
from langchain.document_loaders import PyPDFLoader
from langchain.chains.question_answering import load_qa_chain


def load_pdf_content(urls: Union[List[str], str]) -> str:
    if isinstance(urls, str):
        urls = [urls]

    all_content = []
    for url in urls:
        if not url.endswith('.pdf'):
            raise ValueError('Only PDFs are supported')
        loader = PyPDFLoader(url)
        pages = loader.load_and_split()
        all_content.append('/n'.join([p.page_content for p in pages]))

    return '/n'.join(all_content)


def get_combine_prompt() -> PromptTemplate:
    combine_prompt_template = """Given the following extracted parts of a long document and a question, determine the language of the question & create a final answer in the language the question was asked in. 
    If you don't know the answer, just say that you don't know. Don't try to make up an answer.

    QUESTION: Which state/country's law governs the interpretation of the contract?
    =========
    Content: This Agreement is governed by English law and the parties submit to the exclusive jurisdiction of the English courts in  relation to any dispute (contractual or non-contractual) concerning this Agreement save that either party may apply to any court for an  injunction or other relief to protect its Intellectual Property Rights.

    Content: No Waiver. Failure or delay in exercising any right or remedy under this Agreement shall not constitute a waiver of such (or any other)  right or remedy.\n\n11.7 Severability. The invalidity, illegality or unenforceability of any term (or part of a term) of this Agreement shall not affect the continuation  in force of the remainder of the term (if any) and this Agreement.\n\n11.8 No Agency. Except as expressly stated otherwise, nothing in this Agreement shall create an agency, partnership or joint venture of any  kind between the parties.\n\n11.9 No Third-Party Beneficiaries.

    Content: (b) if Google believes, in good faith, that the Distributor has violated or caused Google to violate any Anti-Bribery Laws (as  defined in Clause 8.5) or that such a violation is reasonably likely to occur,
    =========
    LANGUAGE: English
    FINAL ANSWER: This Agreement is governed by English law.


    QUESTION: Modiji ne kaunse junction kaa naam rename kiya?
    =========
    Content: Friends, in this very July an interesting endeavour has been undertaken, named Azadi Ki Railgadi Aur Railway Station. The objective of this effort is to make people know the role of Indian Railways in the freedom struggle. There are many such railway stations in the country, which are associated with the history of the freedom movement. You too will be surprised to know about these railway stations. Gomoh Junction in Jharkhand is now officially known as Netaji Subhas Chandra Bose Junction Gomoh. Do you know why? Actually at this very station, Netaji Subhash was successful in dodging British officers by boarding the Kalka Mail. All of you must have heard the name of Kakori Railway Station near Lucknow. The names of bravehearts like Ram Prasad Bismil and Ashfaq Ullah Khan are associated with this station. The brave revolutionaries had displayed their might to the British by looting the treasury of the British being carried by train. Whenever you talk to the people of Tamil Nadu, you will get to know about Vanchi Maniyachchi Junction in Thoothukudi district. This station is named after Tamil freedom fighter Vanchinathan ji. This is the same place where Vanchi, 25 years of age then, had punished one British collector for his actions.
    =========
    LANGUAGE: HINDI, ENGLISH
    FINAL_ANSWER: Gomoh junction, jo ki Jarkhand mai hai, abhi Netaji Subash Chandra Bose Junction ke naam se jaana jaega.


    QUESTION: President ne Michael Jackson ke baare mai kya bola?
    =========
    Content: Madam Speaker, Madam Vice President, our First Lady and Second Gentleman. Members of Congress and the Cabinet. Justices of the Supreme Court. My fellow Americans.  \n\nLast year COVID-19 kept us apart. This year we are finally together again. \n\nTonight, we meet as Democrats Republicans and Independents. But most importantly as Americans. \n\nWith a duty to one another to the American people to the Constitution. \n\nAnd with an unwavering resolve that freedom will always triumph over tyranny. \n\nSix days ago, Russia’s Vladimir Putin sought to shake the foundations of the free world thinking he could make it bend to his menacing ways. But he badly miscalculated. \n\nHe thought he could roll into Ukraine and the world would roll over. Instead he met a wall of strength he never imagined. \n\nHe met the Ukrainian people. \n\nFrom President Zelenskyy to every Ukrainian, their fearlessness, their courage, their determination, inspires the world. \n\nGroups of citizens blocking tanks with their bodies. Everyone from students to retirees teachers turned soldiers defending their homeland.

    Content: And we won’t stop. \n\nWe have lost so much to COVID-19. Time with one another. And worst of all, so much loss of life. \n\nLet’s use this moment to reset. Let’s stop looking at COVID-19 as a partisan dividing line and see it for what it is: A God-awful disease.  \n\nLet’s stop seeing each other as enemies, and start seeing each other for who we really are: Fellow Americans.  \n\nWe can’t change how divided we’ve been. But we can change how we move forward—on COVID-19 and other issues we must face together. \n\nI recently visited the New York City Police Department days after the funerals of Officer Wilbert Mora and his partner, Officer Jason Rivera. \n\nThey were responding to a 9-1-1 call when a man shot and killed them with a stolen gun. \n\nOfficer Mora was 27 years old. \n\nOfficer Rivera was 22. \n\nBoth Dominican Americans who’d grown up on the same streets they later chose to patrol as police officers. \n\nI spoke with their families and told them that we are forever in debt for their sacrifice, and we will carry on their mission to restore the trust and safety every community deserves.

    Content: And a proud Ukrainian people, who have known 30 years  of independence, have repeatedly shown that they will not tolerate anyone who tries to take their country backwards.  \n\nTo all Americans, I will be honest with you, as I’ve always promised. A Russian dictator, invading a foreign country, has costs around the world. \n\nAnd I’m taking robust action to make sure the pain of our sanctions  is targeted at Russia’s economy. And I will use every tool at our disposal to protect American businesses and consumers. \n\nTonight, I can announce that the United States has worked with 30 other countries to release 60 Million barrels of oil from reserves around the world.  \n\nAmerica will lead that effort, releasing 30 Million barrels from our own Strategic Petroleum Reserve. And we stand ready to do more if necessary, unified with our allies.  \n\nThese steps will help blunt gas prices here at home. And I know the news about what’s happening can seem alarming. \n\nBut I want you to know that we are going to be okay.
    =========
    LANGUAGE: HINDI, ENGLISH
    FINAL ANSWER: President ne Michael Jackson ko mention nahi kiya.

    QUESTION: {question}
    =========
    {summaries}
    =========
    LANGUAGE:
    FINAL ANSWER:"""

    return PromptTemplate(
        template=combine_prompt_template, input_variables=["summaries", "question"]
    )


def get_qna_chain(llm) -> AnalyzeDocumentChain:
    comnine_prompt = get_combine_prompt()
    qa_chain = load_qa_chain(
        llm, chain_type="map_reduce", combine_prompt=comnine_prompt
    )
    return AnalyzeDocumentChain(combine_docs_chain=qa_chain)
